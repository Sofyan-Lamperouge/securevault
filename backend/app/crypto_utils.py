import os
import hashlib
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend

# ==================== RSA KEY GENERATION ====================
def generate_rsa_keypair():
    """Generate RSA-2048 key pair"""
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )
    public_key = private_key.public_key()
    return private_key, public_key

def serialize_public_key(public_key) -> str:
    """Serialize public key to PEM string"""
    return public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode('utf-8')

def serialize_private_key(private_key) -> bytes:
    """Serialize private key to PEM bytes (without encryption)"""
    return private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )

def deserialize_public_key(public_key_pem: str):
    """Load public key from PEM string"""
    return serialization.load_pem_public_key(
        public_key_pem.encode('utf-8'),
        backend=default_backend()
    )

def deserialize_private_key(private_key_pem: bytes):
    """Load private key from PEM bytes"""
    return serialization.load_pem_private_key(
        private_key_pem,
        password=None,
        backend=default_backend()
    )

# ==================== PBKDF2 (untuk enkripsi private key) ====================
def derive_key_from_password(password: str, salt: bytes, iterations: int = 100000, length: int = 32) -> bytes:
    """Derive encryption key from password using PBKDF2-HMAC-SHA256"""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=length,
        salt=salt,
        iterations=iterations,
        backend=default_backend()
    )
    return kdf.derive(password.encode('utf-8'))

def encrypt_private_key_with_password(private_key_pem: bytes, password: str, salt: bytes = None) -> dict:
    """
    Enkripsi RSA private key dengan password menggunakan AES-256-GCM
    Returns: {
        'encrypted_key': bytes,
        'salt': bytes,
        'nonce': bytes,
        'iterations': int
    }
    """
    if salt is None:
        salt = os.urandom(16)
    
    iterations = 100000
    key = derive_key_from_password(password, salt, iterations)
    nonce = os.urandom(12)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, private_key_pem, None)
    
    return {
        'encrypted_key': ciphertext,
        'salt': salt,
        'nonce': nonce,
        'iterations': iterations
    }

def decrypt_private_key_with_password(encrypted_data: bytes, password: str, salt: bytes, nonce: bytes, iterations: int) -> bytes:
    """Dekripsi RSA private key dengan password"""
    key = derive_key_from_password(password, salt, iterations, 32)
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, encrypted_data, None)

# ==================== AES-GCM untuk file ====================
def generate_session_key() -> bytes:
    """Generate random 32-byte session key for AES-256"""
    return os.urandom(32)

def encrypt_file_aes_gcm(file_data: bytes, session_key: bytes) -> dict:
    """
    Enkripsi file dengan AES-256-GCM
    Returns: {
        'ciphertext': bytes,
        'nonce': bytes
    }
    """
    nonce = os.urandom(12)
    aesgcm = AESGCM(session_key)
    ciphertext = aesgcm.encrypt(nonce, file_data, None)
    return {
        'ciphertext': ciphertext,
        'nonce': nonce
    }

def decrypt_file_aes_gcm(ciphertext: bytes, session_key: bytes, nonce: bytes) -> bytes:
    """Dekripsi file dengan AES-256-GCM"""
    aesgcm = AESGCM(session_key)
    return aesgcm.decrypt(nonce, ciphertext, None)

# ==================== RSA Wrapping/Unwrapping ====================
def wrap_session_key_rsa(session_key: bytes, public_key_pem: str) -> bytes:
    """Enkripsi session key dengan RSA public key (OAEP)"""
    public_key = deserialize_public_key(public_key_pem)
    wrapped = public_key.encrypt(
        session_key,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )
    return wrapped

def unwrap_session_key_rsa(wrapped_key: bytes, private_key_pem: bytes) -> bytes:
    """Dekripsi session key dengan RSA private key (OAEP)"""
    private_key = deserialize_private_key(private_key_pem)
    session_key = private_key.decrypt(
        wrapped_key,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )
    return session_key

# ==================== SHA-256 Hashing ====================
def hash_file_sha256(file_data: bytes) -> str:
    """Hitung SHA-256 hash dari file"""
    return hashlib.sha256(file_data).hexdigest()

def verify_file_integrity(file_data: bytes, expected_hash: str) -> bool:
    """Verifikasi integritas file dengan hash"""
    return hash_file_sha256(file_data) == expected_hash