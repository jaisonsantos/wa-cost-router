"""Script para popular providers iniciais com suporte a multi-tenant."""

import argparse
import uuid

from app.core.database import SessionLocal
from app.models.models import Organization, Provider


DEFAULT_PROVIDERS = [
    {
        "name": "360dialog",
        "type": "whatsapp",
        "base_url": "https://waba.360dialog.io/v1",
        "status": "active",
        "meta": {"description": "360Dialog WhatsApp Business API"},
    },
    {
        "name": "gupshup",
        "type": "whatsapp",
        "base_url": "https://api.gupshup.io/sm/api/v1",
        "status": "active",
        "meta": {"description": "Gupshup WhatsApp Business API"},
    },
]


def seed_providers(org_id: str | None = None) -> None:
    db = SessionLocal()

    try:
        organizations_query = db.query(Organization)

        if org_id:
            try:
                org_uuid = uuid.UUID(org_id)
            except ValueError:
                print(f"❌ Invalid org_id format: {org_id}")
                return

            organizations = organizations_query.filter(Organization.id == org_uuid).all()
            if not organizations:
                print(f"❌ Organization not found for org_id={org_id}")
                return
        else:
            organizations = organizations_query.all()
            if not organizations:
                print("❌ No organizations found. Create an organization before seeding providers.")
                return

        total_created = 0
        created_messages: list[str] = []

        for organization in organizations:
            created_for_org = 0

            for provider_data in DEFAULT_PROVIDERS:
                exists = (
                    db.query(Provider)
                    .filter(
                        Provider.org_id == organization.id,
                        Provider.name == provider_data["name"],
                    )
                    .first()
                )

                if exists:
                    continue

                db.add(Provider(org_id=organization.id, **provider_data))
                created_for_org += 1

            if created_for_org:
                created_messages.append(
                    f"org_id={organization.id} -> {created_for_org} provider(s) created"
                )
                total_created += created_for_org
            else:
                created_messages.append(
                    f"org_id={organization.id} -> providers already seeded"
                )

        if total_created:
            db.commit()
            print("✅ Seeded providers successfully:\n- " + "\n- ".join(created_messages))
        else:
            print("ℹ️ No providers created. " + " | ".join(created_messages))

    except Exception as e:  # noqa: BLE001
        print(f"❌ Error seeding providers: {str(e)}")
        db.rollback()

    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed default providers for an organization")
    parser.add_argument(
        "--org-id",
        dest="org_id",
        help="UUID da organização alvo. Se omitido, aplica para todas as organizações.",
    )
    args = parser.parse_args()
    seed_providers(org_id=args.org_id)
