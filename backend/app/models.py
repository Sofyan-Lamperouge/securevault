from sqlalchemy import Column, Integer, String, DateTime, Text, LargeBinary, ForeignKey, Boolean, BigInteger # type: ignore
from sqlalchemy.sql import func # type: ignore
from sqlalchemy.orm import relationship # type: ignore
from app.database import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    public_key_pem = Column(Text, nullable=False)
    encrypted_private_key = Column(LargeBinary, nullable=False)
    private_key_nonce = Column(String(32), nullable=False)
    salt = Column(String(64), nullable=False)
    pbkdf2_iterations = Column(Integer, default=100000)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    owned_files = relationship("File", back_populates="owner", foreign_keys="File.owner_id")
    file_shares = relationship("FileShare", back_populates="shared_with_user", foreign_keys="FileShare.shared_with_id")
    activities = relationship("ActivityLog", back_populates="user")

class File(Base):
    __tablename__ = "files"
    
    id = Column(Integer, primary_key=True, index=True)
    original_filename = Column(String(255), nullable=False)
    encrypted_filename = Column(String(500), nullable=False)
    file_size = Column(BigInteger, nullable=False)
    file_hash = Column(String(64), nullable=False)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    is_deleted = Column(Boolean, default=False)
    
    owner = relationship("User", back_populates="owned_files", foreign_keys=[owner_id])
    shares = relationship("FileShare", back_populates="file")
    wrapped_keys = relationship("WrappedKey", back_populates="file")

class FileShare(Base):
    __tablename__ = "file_shares"
    
    id = Column(Integer, primary_key=True, index=True)
    file_id = Column(Integer, ForeignKey("files.id"), nullable=False)
    shared_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    shared_with_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    access_type = Column(String(20), default="read")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    file = relationship("File", back_populates="shares")
    shared_by = relationship("User", foreign_keys=[shared_by_id])
    shared_with_user = relationship("User", back_populates="file_shares", foreign_keys=[shared_with_id])

class WrappedKey(Base):
    __tablename__ = "wrapped_keys"
    
    id = Column(Integer, primary_key=True, index=True)
    file_id = Column(Integer, ForeignKey("files.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    wrapped_session_key = Column(LargeBinary, nullable=False)
    is_owner = Column(Boolean, default=False)
    
    file = relationship("File", back_populates="wrapped_keys")
    user = relationship("User")

class ActivityLog(Base):
    __tablename__ = "activity_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    action = Column(String(50), nullable=False)
    file_id = Column(Integer, ForeignKey("files.id"), nullable=True)
    target_user = Column(String(50), nullable=True)
    details = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    user = relationship("User", back_populates="activities")