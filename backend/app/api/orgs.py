from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.core.database import get_db
from app.api.dependencies import get_current_user

router = APIRouter()

class OrgResponse(BaseModel):
    id: str
    name: str
    user_email: str
    role: str

@router.get("/current", response_model=OrgResponse)
def get_current_org(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.models.models import Organization, OrganizationUser, User
    
    org = db.query(Organization).filter(Organization.id == current_user["org_id"]).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    user = db.query(User).filter(User.id == current_user["user_id"]).first()
    org_user = db.query(OrganizationUser).filter(
        OrganizationUser.org_id == org.id,
        OrganizationUser.user_id == user.id
    ).first()
    
    return OrgResponse(
        id=str(org.id),
        name=org.name,
        user_email=user.email,
        role=org_user.role.value
    )
