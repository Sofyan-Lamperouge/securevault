from fastapi import APIRouter, Depends, HTTPException # type: ignore
from sqlalchemy.orm import Session # type: ignore
from pydantic import BaseModel # type: ignore
from datetime import datetime, timedelta
from jose import jwt # type: ignore
import bcrypt # type: ignore
from app.database import get_db
from app.models import User
from app.config import settings
from app.dependencies import get_current_user
from app.crypto_utils import (
    generate_rsa_keypair, serialize_public_key, serialize_private_key,
    encrypt_private_key_with_password
)

router = APIRouter(prefix="/auth", tags=["Authentication"])

class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str

class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    username: str

class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    public_key_pem: str

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

@router.post("/register")
async def register(request: RegisterRequest, db: Session = Depends(get_db)):
    # Cek existing user
    existing = db.query(User).filter(
        (User.username == request.username) | (User.email == request.email)
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username or email already exists")
    
    # Generate RSA key pair
    private_key, public_key = generate_rsa_keypair()
    public_key_pem = serialize_public_key(public_key)
    private_key_pem = serialize_private_key(private_key)
    
    # Enkripsi private key dengan password
    encrypted = encrypt_private_key_with_password(private_key_pem, request.password)
    
    # Hash password untuk login (bcrypt)
    hashed_password = bcrypt.hashpw(request.password.encode('utf-8'), bcrypt.gensalt())
    
    # Simpan user
    new_user = User(
        username=request.username,
        email=request.email,
        password_hash=hashed_password.decode('utf-8'),
        public_key_pem=public_key_pem,
        encrypted_private_key=encrypted['encrypted_key'],
        private_key_nonce=encrypted['nonce'].hex(),
        salt=encrypted['salt'].hex(),
        pbkdf2_iterations=encrypted['iterations']
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return {"message": "User registered successfully", "user_id": new_user.id}

@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == request.username).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if not bcrypt.checkpw(request.password.encode('utf-8'), user.password_hash.encode('utf-8')):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    access_token = create_access_token(data={"sub": str(user.id)})
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        username=user.username
    )

@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        public_key_pem=current_user.public_key_pem
    )