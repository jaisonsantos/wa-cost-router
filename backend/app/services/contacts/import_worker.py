"""Background job that processes contact import CSV files."""

from __future__ import annotations

import csv
import io
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

import redis
from rq import Queue
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.models import (
    ContactImportJob,
    ContactImportStatusEnum,
    ContactStatusEnum,
)
from app.services.contacts.repository import ContactRepository
from app.services.storage import TemporaryObjectStorage


QUEUE_NAME = "default"


def get_queue() -> Queue:
    """Return the queue used for contact import background jobs."""

    connection = redis.from_url(settings.REDIS_URL)
    return Queue(QUEUE_NAME, connection=connection)


def enqueue_contact_import(job_id: uuid.UUID) -> None:
    """Schedule processing of a contact import job."""

    queue = get_queue()
    queue.enqueue(process_contact_import_job, job_id=str(job_id))


@dataclass(slots=True)
class RowValidationError:
    row_number: int
    error: str
    row_data: dict[str, str]


REQUIRED_HEADERS = {"full_name"}


def _normalize_header(raw_headers: Iterable[str] | None) -> set[str]:
    return {header.strip() for header in raw_headers or [] if header}


def _write_error_report(
    errors: list[RowValidationError],
    *,
    fieldnames: list[str],
    storage: TemporaryObjectStorage,
) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=["row_number", "error", *fieldnames],
    )
    writer.writeheader()
    for error in errors:
        payload = {
            "row_number": error.row_number,
            "error": error.error,
            **{key: error.row_data.get(key, "") for key in fieldnames},
        }
        writer.writerow(payload)

    return storage.store_bytes(
        buffer.getvalue().encode("utf-8"),
        prefix="contact-imports",
        suffix=".errors.csv",
    )


def _determine_status(processed: int, errors: int) -> ContactImportStatusEnum:
    if processed > 0 and errors == 0:
        return ContactImportStatusEnum.completed
    if processed > 0 and errors > 0:
        return ContactImportStatusEnum.completed
    return ContactImportStatusEnum.failed


def process_contact_import_job(
    job_id: str | uuid.UUID,
    *,
    storage: TemporaryObjectStorage | None = None,
    session_factory=SessionLocal,
) -> None:
    """Process a contact import job from CSV input."""

    job_uuid = uuid.UUID(str(job_id))
    storage = storage or TemporaryObjectStorage()

    db: Session = session_factory()
    try:
        job = (
            db.query(ContactImportJob)
            .filter(ContactImportJob.id == job_uuid)
            .one_or_none()
        )

        if job is None:
            return

        now = datetime.now(timezone.utc)
        job.status = ContactImportStatusEnum.validating
        job.started_at = now
        db.commit()

        errors: list[RowValidationError] = []
        processed_rows = 0
        total_rows = 0
        raw_fieldnames: list[str] = []

        with storage.open(job.input_uri, "r", encoding="utf-8") as handle:  # type: ignore[arg-type]
            reader = csv.DictReader(handle)
            raw_fieldnames = [name for name in reader.fieldnames or [] if name]
            headers = _normalize_header(raw_fieldnames)

            missing_headers = REQUIRED_HEADERS - headers
            if missing_headers:
                error_message = (
                    "Missing required column(s): "
                    + ", ".join(sorted(missing_headers))
                )
                errors.append(
                    RowValidationError(
                        row_number=1,
                        error=error_message,
                        row_data={},
                    )
                )
            else:
                repo = ContactRepository(db)
                for index, row in enumerate(reader, start=2):
                    total_rows += 1
                    normalized_row = {
                        key: (value or "").strip()
                        for key, value in row.items()
                        if key
                    }
                    validation_errors: list[str] = []

                    identifier = normalized_row.get("external_id")
                    email = normalized_row.get("email")
                    phone = normalized_row.get("phone")
                    status_value = normalized_row.get("status")

                    if not normalized_row.get("full_name"):
                        validation_errors.append("full_name is required")

                    if not email and not phone:
                        validation_errors.append("email or phone must be provided")

                    parsed_status = ContactStatusEnum.active
                    if status_value:
                        try:
                            parsed_status = ContactStatusEnum(status_value)
                        except ValueError:
                            validation_errors.append(
                                f"invalid status '{status_value}'"
                            )

                    if validation_errors:
                        errors.append(
                            RowValidationError(
                                row_number=index,
                                error="; ".join(validation_errors),
                                row_data=normalized_row,
                            )
                        )
                        continue

                    payload = {
                        "org_id": job.org_id,
                        "external_id": identifier or None,
                        "full_name": normalized_row.get("full_name"),
                        "email": email or None,
                        "phone": phone or None,
                        "status": parsed_status,
                        "source": "import",
                        "source_metadata": {"job_id": str(job.id)},
                    }

                    try:
                        repo.create_contact(**payload)
                        processed_rows += 1
                    except IntegrityError as exc:
                        db.rollback()
                        error_detail = str(getattr(exc, "orig", exc))
                        errors.append(
                            RowValidationError(
                                row_number=index,
                                error=f"database integrity error: {error_detail}",
                                row_data=normalized_row,
                            )
                        )

        job.total_rows = total_rows
        job.processed_rows = processed_rows
        job.error_rows = len(errors)
        job.completed_at = datetime.now(timezone.utc)
        job.status = _determine_status(processed_rows, len(errors))

        if errors:
            error_uri = _write_error_report(
                errors,
                fieldnames=raw_fieldnames,
                storage=storage,
            )
            job.error_report_uri = error_uri

        db.commit()
    except Exception:
        db.rollback()
        job = (
            db.query(ContactImportJob)
            .filter(ContactImportJob.id == job_uuid)
            .one_or_none()
        )
        if job is not None:
            job.status = ContactImportStatusEnum.failed
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
        raise
    finally:
        db.close()
