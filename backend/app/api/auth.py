import hashlib
from datetime import datetime, timezone

from email_validator import EmailNotValidError, validate_email
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from pydantic import BaseModel, field_validator

from app.core.database import get_db
from app.core.security import hash_password, verify_password, create_access_token
from app.models.models import (
    Contact,
    ContactChannelOptIn,
    ContactStatusEnum,
    OptInStatusEnum,
    Organization,
    OrganizationUser,
    RoleEnum,
    User,
)

LOCAL_EMAIL_SUFFIX = ".local"


def _normalize_email(value: str) -> str:
    """Validate and canonicalize user supplied email addresses.

    The default validator rejects addresses that use development-only domains
    such as ``*.local``. For those we validate the local part using the
    library and then stitch it back together with a lower-cased domain so the
    rest of the application can keep treating emails as canonical strings.
    """

    stripped = value.strip()
    try:
        result = validate_email(stripped, check_deliverability=False)
        return result.email
    except EmailNotValidError as exc:
        local_part, sep, domain = stripped.rpartition("@")
        if (
            sep == "@"
            and domain
            and domain.lower().endswith(LOCAL_EMAIL_SUFFIX)
        ):
            normalized_domain = domain.lower()
            domain_without_suffix = normalized_domain[: -len(LOCAL_EMAIL_SUFFIX)]
            if not domain_without_suffix or any(
                not label for label in domain_without_suffix.split(".")
            ):
                raise ValueError("Invalid email domain")
            try:
                pseudo_result = validate_email(
                    f"{local_part}@example.com", check_deliverability=False
                )
            except EmailNotValidError as inner_exc:  # pragma: no cover - FastAPI handles response
                raise ValueError(str(inner_exc)) from inner_exc
            normalized_local = pseudo_result.local_part
            return f"{normalized_local}@{normalized_domain}"
        raise ValueError(str(exc)) from exc

router = APIRouter()


def _bootstrap_demo_contact(db: Session, org_id) -> None:
    """Ensure a demo contact with an active WhatsApp opt-in exists for the org."""

    normalized_phone = "+5511999999999"
    now = datetime.now(timezone.utc)
    source_metadata = {"bootstrap": "register"}

    contact = (
        db.query(Contact)
        .filter(Contact.org_id == org_id)
        .filter(Contact.phone.isnot(None))
        .filter(func.lower(Contact.phone) == normalized_phone.lower())
        .first()
    )

    if not contact:
        contact = Contact(
            org_id=org_id,
            full_name="John Customer",
            first_name="John",
            last_name="Customer",
            email="john.customer@example.com",
            phone=normalized_phone,
            status=ContactStatusEnum.active,
            source="bootstrap",
            source_metadata=source_metadata,
            proof_hash=hashlib.sha256(
                f"contact:{org_id}:{normalized_phone}:bootstrap".encode()
            ).hexdigest(),
            created_at=now,
            updated_at=now,
        )
        db.add(contact)
        db.flush()

    opt_in = (
        db.query(ContactChannelOptIn)
        .filter(ContactChannelOptIn.org_id == org_id)
        .filter(ContactChannelOptIn.contact_id == contact.id)
        .filter(ContactChannelOptIn.channel == "whatsapp")
        .filter(func.lower(ContactChannelOptIn.channel_address) == normalized_phone.lower())
        .filter(ContactChannelOptIn.version == 1)
        .first()
    )

    if not opt_in:
        opt_in = ContactChannelOptIn(
            org_id=org_id,
            contact_id=contact.id,
            channel="whatsapp",
            channel_address=normalized_phone,
            status=OptInStatusEnum.granted,
            version=1,
            legal_basis="opt_in",
            captured_at=now,
            source="bootstrap",
            source_metadata=source_metadata,
            evidence_uri="https://example.com/proof/whatsapp-opt-in-john",
            proof_hash=hashlib.sha256(
                f"optin:{org_id}:{normalized_phone}:bootstrap".encode()
            ).hexdigest(),
            created_at=now,
            updated_at=now,
        )
        db.add(opt_in)

class RegisterRequest(BaseModel):
    email: str
    password: str
    org_name: str

    @field_validator("email")
    @classmethod
    def validate_email_address(cls, value: str) -> str:
        return _normalize_email(value)


class LoginRequest(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def validate_email_address(cls, value: str) -> str:
        return _normalize_email(value)

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

@router.post("/register", response_model=TokenResponse)
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    # Check if user exists
    existing = db.query(User).filter(User.email == req.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create org
    org = Organization(name=req.org_name)
    db.add(org)
    db.flush()
    
    # Create user
    user = User(email=req.email, password_hash=hash_password(req.password))
    db.add(user)
    db.flush()
    
    # Link user to org as owner
    org_user = OrganizationUser(org_id=org.id, user_id=user.id, role=RoleEnum.owner)
    db.add(org_user)

    _bootstrap_demo_contact(db, org.id)

    db.commit()
    
    # Create token
    token = create_access_token({"sub": str(user.id), "org_id": str(org.id)})
    return TokenResponse(access_token=token)

@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email).first()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Get user's first org
    org_user = db.query(OrganizationUser).filter(OrganizationUser.user_id == user.id).first()
    if not org_user:
        raise HTTPException(status_code=400, detail="User not linked to any organization")
    
    token = create_access_token({"sub": str(user.id), "org_id": str(org_user.org_id)})
    return TokenResponse(access_token=token)
