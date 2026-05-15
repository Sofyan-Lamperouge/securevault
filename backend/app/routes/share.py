from fastapi import APIRouter, Depends, HTTPException # type: ignore
from sqlalchemy.orm import Session # type: ignore
from typing import List
from pydantic import BaseModel # type: ignore
from app.database import get_db
from app.models import User, File as FileModel, WrappedKey, FileShare, ActivityLog
from app.dependencies import get_current_user
from app.crypto_utils import (
    unwrap_session_key_rsa, wrap_session_key_rsa,
    decrypt_private_key_with_password
)

router = APIRouter(prefix="/share", tags=["Sharing"])

# ==================== Pydantic Models ====================
class ShareRequest(BaseModel):
    target_username: str
    access_type: str = "read_only"  # read_only (bisa ditambah write nanti)

class ShareMultipleRequest(BaseModel):
    target_usernames: List[str]
    access_type: str = "read_only"

class ShareInfo(BaseModel):
    file_id: int
    filename: str
    shared_with: str
    access_type: str
    shared_at: str

class SharedFileInfo(BaseModel):
    file_id: int
    filename: str
    owner: str
    file_size: int
    shared_at: str

# ==================== Endpoints ====================
@router.post("/{file_id}")
async def share_file(
    file_id: int,
    request: ShareRequest,
    password: str,  # Password pemilik untuk dekripsi private key
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Berbagi file ke user lain (key wrapping)
    - Hanya pemilik file yang bisa berbagi
    - Session key dienkripsi ulang dengan RSA publik penerima
    """
    
    # 1. Cek apakah file ada
    file_entry = db.query(FileModel).filter(FileModel.id == file_id).first()
    if not file_entry:
        raise HTTPException(status_code=404, detail="File not found")
    
    # 2. Cek apakah user adalah pemilik file
    if file_entry.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only owner can share this file")
    
    # 3. Cek target user
    target_user = db.query(User).filter(User.username == request.target_username).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="Target user not found")
    
    # 4. Tidak bisa share dengan diri sendiri
    if target_user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot share with yourself")
    
    # 5. Cek apakah sudah pernah di-share
    existing_share = db.query(FileShare).filter(
        FileShare.file_id == file_id,
        FileShare.shared_with_id == target_user.id
    ).first()
    if existing_share:
        raise HTTPException(status_code=400, detail="File already shared with this user")
    
    # 6. Ambil wrapped key pemilik (untuk mendapatkan session key asli)
    owner_wrapped = db.query(WrappedKey).filter(
        WrappedKey.file_id == file_id,
        WrappedKey.user_id == current_user.id,
        WrappedKey.is_owner == True
    ).first()
    
    if not owner_wrapped:
        raise HTTPException(status_code=404, detail="Owner key not found")
    
    # 7. Dekripsi private key pemilik dengan password
    try:
        private_key_pem = decrypt_private_key_with_password(
            current_user.encrypted_private_key,
            password,
            bytes.fromhex(current_user.salt),
            bytes.fromhex(current_user.private_key_nonce),
            current_user.pbkdf2_iterations
        )
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid password")
    
    # 8. Unwrap session key asli (dekripsi dengan private key pemilik)
    try:
        session_key = unwrap_session_key_rsa(owner_wrapped.wrapped_session_key, private_key_pem)
    except Exception as e:
        raise HTTPException(status_code=400, detail="Failed to unwrap session key")
    
    # 9. Wrap session key dengan public key target user
    wrapped_for_target = wrap_session_key_rsa(session_key, target_user.public_key_pem)
    
    # 10. Simpan wrapped key untuk target user
    wrapped_entry = WrappedKey(
        file_id=file_id,
        user_id=target_user.id,
        wrapped_session_key=wrapped_for_target,
        is_owner=False
    )
    db.add(wrapped_entry)
    
    # 11. Simpan share relationship
    share_entry = FileShare(
        file_id=file_id,
        shared_by_id=current_user.id,
        shared_with_id=target_user.id,
        access_type=request.access_type
    )
    db.add(share_entry)
    
    # 12. Log aktivitas
    log = ActivityLog(
        user_id=current_user.id,
        action="SHARE",
        file_id=file_id,
        target_user=target_user.username,
        details=f"Shared {file_entry.original_filename} with {target_user.username}"
    )
    db.add(log)
    
    db.commit()
    
    return {
        "message": f"File shared with {target_user.username}",
        "file_id": file_id,
        "shared_with": target_user.username
    }


@router.post("/{file_id}/share-multiple")
async def share_file_multiple(
    file_id: int,
    request: ShareMultipleRequest,
    password: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Berbagi file ke banyak user sekaligus (fitur pengembangan)
    """
    results = []
    for username in request.target_usernames:
        try:
            # Panggil fungsi share untuk masing-masing user
            share_req = ShareRequest(target_username=username, access_type=request.access_type)
            result = await share_file(file_id, share_req, password, current_user, db)
            results.append({"username": username, "status": "success"})
        except HTTPException as e:
            results.append({"username": username, "status": "failed", "reason": e.detail})
        except Exception as e:
            results.append({"username": username, "status": "failed", "reason": str(e)})
    
    return {"results": results}


@router.get("/my-shares")
async def list_my_shares(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Daftar file yang saya share ke orang lain
    """
    shares = db.query(FileShare).filter(FileShare.shared_by_id == current_user.id).all()
    
    result = []
    for s in shares:
        file_entry = db.query(FileModel).filter(FileModel.id == s.file_id).first()
        target_user = db.query(User).filter(User.id == s.shared_with_id).first()
        
        if file_entry and target_user:
            result.append(ShareInfo(
                file_id=file_entry.id,
                filename=file_entry.original_filename,
                shared_with=target_user.username,
                access_type=s.access_type,
                shared_at=s.created_at.isoformat()
            ))
        elif file_entry is None:
            # File sudah dihapus, hapus juga share record-nya
            db.delete(s)
            db.commit()
    
    return result


@router.get("/shared-with-me")
async def list_shared_with_me(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Daftar file yang dishare ke saya oleh orang lain
    """
    shares = db.query(FileShare).filter(FileShare.shared_with_id == current_user.id).all()
    
    result = []
    for s in shares:
        file_entry = db.query(FileModel).filter(FileModel.id == s.file_id).first()
        owner = db.query(User).filter(User.id == s.shared_by_id).first()
        
        if file_entry and owner:
            result.append(SharedFileInfo(
                file_id=file_entry.id,
                filename=file_entry.original_filename,
                owner=owner.username,
                file_size=file_entry.file_size,
                shared_at=s.created_at.isoformat()
            ))
        elif file_entry is None:
            # File sudah dihapus, hapus juga share record-nya
            db.delete(s)
            db.commit()
    
    return result


@router.delete("/{file_id}/user/{username}")
async def revoke_access(
    file_id: int,
    username: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Cabut akses user tertentu terhadap file
    - Hanya pemilik file yang bisa mencabut akses
    """
    # Cek file dan kepemilikan
    file_entry = db.query(FileModel).filter(FileModel.id == file_id).first()
    if not file_entry:
        raise HTTPException(status_code=404, detail="File not found")
    
    if file_entry.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only owner can revoke access")
    
    # Cek target user
    target_user = db.query(User).filter(User.username == username).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Hapus share relationship
    deleted_shares = db.query(FileShare).filter(
        FileShare.file_id == file_id,
        FileShare.shared_with_id == target_user.id
    ).delete()
    
    if deleted_shares == 0:
        raise HTTPException(status_code=404, detail="User does not have access to this file")
    
    # Hapus wrapped key target user
    db.query(WrappedKey).filter(
        WrappedKey.file_id == file_id,
        WrappedKey.user_id == target_user.id
    ).delete()
    
    # Log aktivitas
    log = ActivityLog(
        user_id=current_user.id,
        action="REVOKE",
        file_id=file_id,
        target_user=username,
        details=f"Revoked {file_entry.original_filename} access from {username}"
    )
    db.add(log)
    db.commit()
    
    return {"message": f"Access revoked for {username}"}


@router.get("/check-access/{file_id}")
async def check_access(
    file_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Cek apakah user memiliki akses ke file tertentu
    """
    file_entry = db.query(FileModel).filter(FileModel.id == file_id).first()
    if not file_entry:
        raise HTTPException(status_code=404, detail="File not found")
    
    is_owner = (file_entry.owner_id == current_user.id)
    
    if is_owner:
        return {"has_access": True, "role": "owner"}
    
    share = db.query(FileShare).filter(
        FileShare.file_id == file_id,
        FileShare.shared_with_id == current_user.id
    ).first()
    
    if share:
        return {"has_access": True, "role": "shared", "access_type": share.access_type}
    
    return {"has_access": False, "role": None}