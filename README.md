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
