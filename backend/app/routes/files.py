import os
import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File # type: ignore
from fastapi.responses import StreamingResponse # type: ignore
from sqlalchemy.orm import Session # type: ignore
from typing import List
from pydantic import BaseModel # type: ignore
from io import BytesIO
from app.database import get_db
from app.models import User, File as FileModel, WrappedKey, ActivityLog, FileShare
from app.dependencies import get_current_user
from app.crypto_utils import (
    generate_session_key, encrypt_file_aes_gcm, wrap_session_key_rsa,
    hash_file_sha256, decrypt_file_aes_gcm, unwrap_session_key_rsa,
    decrypt_private_key_with_password, verify_file_integrity
)
from app.config import settings

router = APIRouter(prefix="/files", tags=["Files"])

class FileInfo(BaseModel):
    id: int
    original_filename: str
    file_size: int
    file_hash: str
    created_at: str
    is_owner: bool
    shared_with: List[str] = []

class FileListResponse(BaseModel):
    owned: List[FileInfo]
    shared_with_me: List[FileInfo]

@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload file - dienkripsi dengan AES-256-GCM"""
    
    # Baca file
    file_data = await file.read()
    
    if len(file_data) == 0:
        raise HTTPException(status_code=400, detail="File is empty")
    
    # 1. Hitung hash plaintext untuk verifikasi integritas
    file_hash = hash_file_sha256(file_data)
    
    # 2. Generate session key acak (untuk AES-256)
    session_key = generate_session_key()
    
    # 3. Enkripsi file dengan AES-256-GCM
    encrypted = encrypt_file_aes_gcm(file_data, session_key)
    
    # 4. Simpan ke disk dengan format: nonce (12 byte) + ciphertext
    encrypted_filename = f"{uuid.uuid4().hex}.enc"
    storage_path = os.path.join(settings.STORAGE_PATH, encrypted_filename)
    with open(storage_path, "wb") as f:
        f.write(encrypted['nonce'] + encrypted['ciphertext'])
    
    # 5. Wrap session key dengan RSA public key pemilik
    wrapped_key = wrap_session_key_rsa(session_key, current_user.public_key_pem)
    
    # 6. Simpan metadata ke database
    new_file = FileModel(
        original_filename=file.filename,
        encrypted_filename=encrypted_filename,
        file_size=len(file_data),
        file_hash=file_hash,
        owner_id=current_user.id
    )
    db.add(new_file)
    db.flush()  # Dapatkan ID file
    
    # 7. Simpan wrapped key untuk pemilik
    wrapped_entry = WrappedKey(
        file_id=new_file.id,
        user_id=current_user.id,
        wrapped_session_key=wrapped_key,
        is_owner=True
    )
    db.add(wrapped_entry)
    
    # 8. Log aktivitas
    log = ActivityLog(
        user_id=current_user.id,
        action="UPLOAD",
        file_id=new_file.id,
        details=f"Uploaded {file.filename} ({len(file_data)} bytes)"
    )
    db.add(log)
    
    db.commit()
    
    return {
        "message": "File uploaded successfully",
        "file_id": new_file.id,
        "file_hash": file_hash
    }

@router.get("/", response_model=FileListResponse)
async def list_files(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Daftar file milik sendiri dan file yang dishare ke saya"""
    
    # File yang dimiliki (owned)
    owned = db.query(FileModel).filter(
        FileModel.owner_id == current_user.id,
        FileModel.is_deleted == False
    ).all()
    
    # File yang dishare ke saya (shared_with_me)
    shares = db.query(FileShare).filter(
        FileShare.shared_with_id == current_user.id
    ).all()
    shared_file_ids = [s.file_id for s in shares]
    shared_files = db.query(FileModel).filter(
        FileModel.id.in_(shared_file_ids) if shared_file_ids else False,
        FileModel.is_deleted == False
    ).all() if shared_file_ids else []
    
    # Siapkan response untuk owned files
    owned_list = []
    for f in owned:
        # Cari siapa saja yang diberi akses ke file ini
        share_list = db.query(FileShare).filter(FileShare.file_id == f.id).all()
        shared_with_names = []
        for s in share_list:
            user = db.query(User).filter(User.id == s.shared_with_id).first()
            if user:
                shared_with_names.append(user.username)
        
        owned_list.append(FileInfo(
            id=f.id,
            original_filename=f.original_filename,
            file_size=f.file_size,
            file_hash=f.file_hash,
            created_at=f.created_at.isoformat(),
            is_owner=True,
            shared_with=shared_with_names
        ))
    
    # Siapkan response untuk shared files
    shared_list = []
    for f in shared_files:
        shared_list.append(FileInfo(
            id=f.id,
            original_filename=f.original_filename,
            file_size=f.file_size,
            file_hash=f.file_hash,
            created_at=f.created_at.isoformat(),
            is_owner=False,
            shared_with=[]
        ))
    
    return FileListResponse(owned=owned_list, shared_with_me=shared_list)

@router.get("/download/{file_id}")
async def download_file(
    file_id: int,
    password: str,  # Password user untuk dekripsi private key
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Download file - dekripsi dengan RSA private key + verifikasi integritas"""
    
    # Cek apakah file ada
    file_entry = db.query(FileModel).filter(FileModel.id == file_id).first()
    if not file_entry or file_entry.is_deleted:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Cek akses (apakah pemilik atau menerima share)
    is_owner = (current_user.id == file_entry.owner_id)
    
    if not is_owner:
        share = db.query(FileShare).filter(
            FileShare.file_id == file_id,
            FileShare.shared_with_id == current_user.id
        ).first()
        if not share:
            raise HTTPException(status_code=403, detail="Access denied")
    
    # Ambil wrapped key untuk user ini
    wrapped_entry = db.query(WrappedKey).filter(
        WrappedKey.file_id == file_id,
        WrappedKey.user_id == current_user.id
    ).first()
    
    if not wrapped_entry:
        raise HTTPException(status_code=403, detail="No key found for this user")
    
    # Baca ciphertext dari disk
    storage_path = os.path.join(settings.STORAGE_PATH, file_entry.encrypted_filename)
    if not os.path.exists(storage_path):
        raise HTTPException(status_code=404, detail="File not found on server")
    
    with open(storage_path, "rb") as f:
        encrypted_blob = f.read()
    
    # Ekstrak nonce (12 byte pertama) dan ciphertext
    nonce = encrypted_blob[:12]
    ciphertext = encrypted_blob[12:]
    
    # Dekripsi private key user dengan password
    try:
        private_key_pem = decrypt_private_key_with_password(
            current_user.encrypted_private_key,
            password,
            bytes.fromhex(current_user.salt),
            bytes.fromhex(current_user.private_key_nonce),
            current_user.pbkdf2_iterations
        )
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid password or corrupted private key")
    
    # Unwrap session key
    try:
        session_key = unwrap_session_key_rsa(wrapped_entry.wrapped_session_key, private_key_pem)
    except Exception as e:
        raise HTTPException(status_code=400, detail="Failed to unwrap session key")
    
    # Dekripsi file
    try:
        plaintext = decrypt_file_aes_gcm(ciphertext, session_key, nonce)
    except Exception as e:
        raise HTTPException(status_code=400, detail="File integrity check failed - file may be corrupted")
    
    # Verifikasi integritas dengan SHA-256
    if not verify_file_integrity(plaintext, file_entry.file_hash):
        raise HTTPException(status_code=400, detail="Integrity verification failed - file hash mismatch")
    
    # Log aktivitas
    log = ActivityLog(
        user_id=current_user.id,
        action="DOWNLOAD",
        file_id=file_id,
        details=f"Downloaded {file_entry.original_filename}"
    )
    db.add(log)
    db.commit()
    
    # Return file sebagai streaming response
    return StreamingResponse(
        BytesIO(plaintext),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename={file_entry.original_filename}"}
    )

@router.get("/preview/{file_id}")
async def preview_file(
    file_id: int,
    password: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Preview file - mengembalikan file plaintext dengan MIME type yang sesuai
    untuk ditampilkan di browser (teks/gambar)
    """
    
    # Cek apakah file ada
    file_entry = db.query(FileModel).filter(FileModel.id == file_id).first()
    if not file_entry or file_entry.is_deleted:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Cek akses (apakah pemilik atau menerima share)
    is_owner = (current_user.id == file_entry.owner_id)
    
    if not is_owner:
        share = db.query(FileShare).filter(
            FileShare.file_id == file_id,
            FileShare.shared_with_id == current_user.id
        ).first()
        if not share:
            raise HTTPException(status_code=403, detail="Access denied")
    
    # Ambil wrapped key untuk user ini
    wrapped_entry = db.query(WrappedKey).filter(
        WrappedKey.file_id == file_id,
        WrappedKey.user_id == current_user.id
    ).first()
    
    if not wrapped_entry:
        raise HTTPException(status_code=403, detail="No key found for this user")
    
    # Baca ciphertext dari disk
    storage_path = os.path.join(settings.STORAGE_PATH, file_entry.encrypted_filename)
    if not os.path.exists(storage_path):
        raise HTTPException(status_code=404, detail="File not found on server")
    
    with open(storage_path, "rb") as f:
        encrypted_blob = f.read()
    
    # Ekstrak nonce dan ciphertext
    nonce = encrypted_blob[:12]
    ciphertext = encrypted_blob[12:]
    
    # Dekripsi private key user dengan password
    try:
        private_key_pem = decrypt_private_key_with_password(
            current_user.encrypted_private_key,
            password,
            bytes.fromhex(current_user.salt),
            bytes.fromhex(current_user.private_key_nonce),
            current_user.pbkdf2_iterations
        )
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid password")
    
    # Unwrap session key
    try:
        session_key = unwrap_session_key_rsa(wrapped_entry.wrapped_session_key, private_key_pem)
    except Exception:
        raise HTTPException(status_code=400, detail="Failed to unwrap session key")
    
    # Dekripsi file
    try:
        plaintext = decrypt_file_aes_gcm(ciphertext, session_key, nonce)
    except Exception:
        raise HTTPException(status_code=400, detail="File integrity check failed")
    
    # Verifikasi integritas
    if not verify_file_integrity(plaintext, file_entry.file_hash):
        raise HTTPException(status_code=400, detail="Integrity verification failed")
    
    # Log aktivitas preview
    log = ActivityLog(
        user_id=current_user.id,
        action="PREVIEW",
        file_id=file_id,
        details=f"Previewed {file_entry.original_filename}"
    )
    db.add(log)
    db.commit()
    
    # Tentukan MIME type berdasarkan ekstensi file
    filename = file_entry.original_filename.lower()
    if filename.endswith('.txt'):
        media_type = "text/plain"
    elif filename.endswith('.jpg') or filename.endswith('.jpeg'):
        media_type = "image/jpeg"
    elif filename.endswith('.png'):
        media_type = "image/png"
    elif filename.endswith('.gif'):
        media_type = "image/gif"
    elif filename.endswith('.pdf'):
        media_type = "application/pdf"
    elif filename.endswith('.html') or filename.endswith('.htm'):
        media_type = "text/html"
    else:
        media_type = "application/octet-stream"
    
    return StreamingResponse(
        BytesIO(plaintext),
        media_type=media_type,
        headers={"Content-Disposition": f"inline; filename={file_entry.original_filename}"}
    )

@router.delete("/{file_id}")
async def delete_file(
    file_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Hapus file - hapus dari disk, DB, dan semua key material"""
    
    file_entry = db.query(FileModel).filter(FileModel.id == file_id).first()
    if not file_entry:
        raise HTTPException(status_code=404, detail="File not found")
    
    if file_entry.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only owner can delete this file")
    
    # Hapus file dari disk
    storage_path = os.path.join(settings.STORAGE_PATH, file_entry.encrypted_filename)
    if os.path.exists(storage_path):
        os.remove(storage_path)
    
    # Hapus dari database 
    db.query(ActivityLog).filter(ActivityLog.file_id == file_id).delete()
    db.query(WrappedKey).filter(WrappedKey.file_id == file_id).delete()
    db.query(FileShare).filter(FileShare.file_id == file_id).delete()
    db.delete(file_entry)
    
    db.commit()  
    
    return {"message": "File deleted successfully"}