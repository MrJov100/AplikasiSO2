"""Autentikasi: hash kata sandi dan token akses.

Kata sandi disimpan sebagai hash bcrypt, sesuai komentar kolom
pengguna.kata_sandi_hash pada DDL. Kata sandi polos tidak pernah disimpan
maupun dicatat di log.
"""
import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from slowapi import Limiter
from slowapi.util import get_remote_address

# Kunci penanda token. Untuk penerapan sungguhan wajib diisi lewat .env;
# nilai bawaan hanya supaya aplikasi tetap jalan saat pengembangan.
KUNCI = os.getenv("KUNCI_TOKEN", "ganti-kunci-ini-pada-env")
ALGORITMA = "HS256"
MASA_BERLAKU_JAM = int(os.getenv("MASA_TOKEN_JAM", "12"))

skema_oauth = OAuth2PasswordBearer(tokenUrl="api/auth/login", auto_error=False)

# Pembatas laju login tinggal di sini, bukan di api/main.py, supaya controller
# dapat memakainya tanpa mengimpor main — main sendiri mengimpor controller,
# jadi impor baliknya akan memutar.
BATAS_MASUK = os.getenv("BATAS_LAJU_MASUK", "10/minute")
BATAS_UMUM = os.getenv("BATAS_LAJU_UMUM", "60/minute")

# Satu objek dipakai seluruh aplikasi: app.state.limiter di main.py menunjuk ke
# objek ini, dan dekorator @batas_masuk() mendaftar padanya juga.
limiter = Limiter(key_func=get_remote_address, default_limits=[BATAS_UMUM])


def batas_masuk():
    """Dekorator pembatas laju untuk endpoint login."""
    return limiter.limit(BATAS_MASUK)


def hash_kata_sandi(kata_sandi: str) -> str:
    """Mengubah kata sandi polos menjadi hash bcrypt untuk disimpan."""
    return bcrypt.hashpw(kata_sandi.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def periksa_kata_sandi(kata_sandi: str, hash_tersimpan: str) -> bool:
    """Memeriksa kecocokan kata sandi polos dengan hash tersimpan; False bila hash tidak valid."""
    try:
        return bcrypt.checkpw(kata_sandi.encode("utf-8"),
                              hash_tersimpan.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def buat_token(pengguna) -> str:
    """Menerbitkan token JWT berisi identitas pengguna dan waktu kedaluwarsa."""
    kedaluwarsa = datetime.now(timezone.utc) + timedelta(hours=MASA_BERLAKU_JAM)
    return jwt.encode({
        "sub": str(pengguna["id_pengguna"]),
        "username": pengguna["username"],
        "nama_lengkap": pengguna["nama_lengkap"],
        "peran": pengguna["peran"],
        "exp": kedaluwarsa,
    }, KUNCI, algorithm=ALGORITMA)


def pengguna_aktif(token: str = Depends(skema_oauth)):
    """Dependency FastAPI: mengembalikan data pengguna dari token, atau menolak."""
    galat = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Tidak terautentikasi. Masuk terlebih dahulu.",
        headers={"WWW-Authenticate": "Bearer"})
    if not token:
        raise galat
    try:
        isi = jwt.decode(token, KUNCI, algorithms=[ALGORITMA])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401,
                            detail="Sesi berakhir. Silakan masuk kembali.")
    except jwt.PyJWTError:
        raise galat
    return {"id_pengguna": int(isi["sub"]), "username": isi["username"],
            "nama_lengkap": isi["nama_lengkap"], "peran": isi["peran"]}
