from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from app.core.database import get_db
from app.core.security import hash_password, verify_password, create_access_token
from app.models.models import User, Organization, OrganizationUser, RoleEnum

router = APIRouter()

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    org_name: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

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
