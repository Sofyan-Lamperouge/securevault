# 🔐 SecureVault

Sistem manajemen file terenkripsi.

## Fitur

- Registrasi + Login
- Upload/Download file 
- Preview file (teks, gambar, PDF)
- Share file ke user lain 
- Share multiple user sekaligus
- Revoke akses
- Riwayat aktivitas
- Hapus file

## Tech Stack

| Backend | Frontend | Database |
|---------|----------|----------|
| Python + FastAPI | React + Tailwind | MySQL |

## Cara Menjalankan

### 1. Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Mac/Linux
pip install -r requirements.txt
```

Buat file .env:

```
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=
DB_NAME=securevault_db
SECRET_KEY=ganti_dengan_random_string
```

Jalankan:

```bash
uvicorn app.main:app --reload --port 8000
```

### 2. Frontend

```bash
cd frontend
npm install
npm start
```

### 3. Database

```sql
CREATE DATABASE securevault_db;
```

## Akses 

| Komponen | URL |
|----------|-----|
| Frontend | http://localhost:3000 |
| API Docs | http://localhost:8000/docs |

## Video
[Video Demo SecureVault](https://drive.google.com/file/d/1pP6hYOt4-c1VVXF6PlO096O8yyjnTlE5/view?usp=drivesdk)
