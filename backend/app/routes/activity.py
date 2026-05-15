from fastapi import APIRouter, Depends, HTTPException # type: ignore
from sqlalchemy.orm import Session # type: ignore
from typing import List
from pydantic import BaseModel # type: ignore
from datetime import datetime
from app.database import get_db
from app.models import User, ActivityLog, File as FileModel
from app.dependencies import get_current_user

router = APIRouter(prefix="/activity", tags=["Activity"])

class ActivityInfo(BaseModel):
    id: int
    action: str
    file_id: int
    filename: str | None
    target_user: str | None
    details: str
    created_at: str

@router.get("/", response_model=List[ActivityInfo])
async def get_my_activities(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = 50
):
    """Get activity log for current user"""
    
    logs = db.query(ActivityLog).filter(
        ActivityLog.user_id == current_user.id
    ).order_by(ActivityLog.created_at.desc()).limit(limit).all()
    
    result = []
    for log in logs:
        filename = None
        if log.file_id:
            file_entry = db.query(FileModel).filter(FileModel.id == log.file_id).first()
            if file_entry:
                filename = file_entry.original_filename
        
        result.append(ActivityInfo(
            id=log.id,
            action=log.action,
            file_id=log.file_id or 0,
            filename=filename,
            target_user=log.target_user,
            details=log.details or "",
            created_at=log.created_at.isoformat()
        ))
    
    return result