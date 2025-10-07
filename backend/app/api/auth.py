from email_validator import EmailNotValidError, validate_email
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, field_validator

from app.core.database import get_db
from app.core.security import hash_password, verify_password, create_access_token
from app.models.models import User, Organization, OrganizationUser, RoleEnum

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
