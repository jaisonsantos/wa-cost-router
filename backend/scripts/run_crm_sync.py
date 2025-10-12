"""CLI para executar sincronização incremental de contatos CRM."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from typing import Iterable, Optional
from uuid import UUID

from app.core.database import SessionLocal
from app.services.crm import CRMIncrementalSyncService, SyncResult, build_default_registry


def _parse_since(value: Optional[str]) -> Optional[datetime]:
    if value in (None, ""):
        return None

    normalized = value
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"

    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Executa uma iteração de polling CRM e imprime o resumo do resultado.",
    )
    parser.add_argument(
        "--provider",
        required=True,
        help="Slug do provedor registrado em Provider.meta.slug.",
    )
    parser.add_argument(
        "--org-id",
        required=True,
        help="Identificador UUID da organização proprietária.",
    )
    parser.add_argument(
        "--since",
        default=None,
        help="Timestamp ISO-8601 para sobrescrever o cursor incremental (opcional).",
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=None,
        help="Quantidade máxima de registros por página ao consultar o provedor.",
    )
    return parser


def _serialize_result(result: SyncResult) -> dict:
    last_change = (
        result.last_change_at.astimezone(timezone.utc).isoformat()
        if result.last_change_at
        else None
    )
    return {
        "processed_contacts": result.processed_contacts,
        "has_more": result.has_more,
        "next_cursor": result.next_cursor,
        "last_change_at": last_change,
        "origin": result.origin,
    }


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        org_id = UUID(str(args.org_id))
    except ValueError as exc:
        parser.error(f"--org-id inválido: {exc}")

    since = None
    if args.since is not None:
        try:
            since = _parse_since(args.since)
        except ValueError as exc:
            parser.error(f"--since inválido: {exc}")

    db = SessionLocal()
    try:
        service = CRMIncrementalSyncService(db, registry=build_default_registry())
        result = service.run_polling_cycle(
            org_id=org_id,
            provider_slug=args.provider,
            since=since,
            page_size=args.page_size,
        )
    finally:
        db.close()

    print(json.dumps(_serialize_result(result), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
