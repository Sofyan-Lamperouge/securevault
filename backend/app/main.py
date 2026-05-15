from fastapi import FastAPI # type: ignore
from fastapi.middleware.cors import CORSMiddleware # type: ignore
from app.database import engine, Base
from app.routes import auth, files, share  
from app.routes import auth, files, share, activity

# Buat tabel database
Base.metadata.create_all(bind=engine)

app = FastAPI(title="SecureVault API", version="1.0.0")

# CORS untuk React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth.router)
app.include_router(files.router)
app.include_router(share.router)
app.include_router(activity.router)

@app.get("/")
def root():
    return {"message": "SecureVault API is running"}

@app.get("/health")
def health():
    return {"status": "ok"}