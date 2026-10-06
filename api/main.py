"""Titik masuk FastAPI.

    uvicorn api.main:app --reload
    uvicorn api.main:app --host 0.0.0.0 --port 8000     (agar bisa diakses dari
                                                         komputer lain di jaringan)

Dokumentasi endpoint otomatis tersedia di http://localhost:8000/docs — berguna
saat pengujian black box Fase 5 dan saat demonstrasi ke DLH.

Bila folder antarmuka/dist sudah ada (hasil build React), berkasnya disajikan
langsung oleh FastAPI. Dengan begitu seluruh aplikasi berjalan pada SATU alamat
dan satu proses, yang jauh lebih mudah didemonstrasikan daripada dua server.
"""
import sys
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

AKAR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AKAR))

from api.controller import SEMUA_ROUTER                   # noqa: E402
from api import keamanan                                  # noqa: E402
import basis_data as bd                                   # noqa: E402
import model as md                                        # noqa: E402
from konfigurasi import KODE_SEL                          # noqa: E402

app = FastAPI(
    title="Prediksi Konsentrasi SO₂ Jabodetabek",
    description="Skripsi Jovandi Todana — 535230027 — Teknik Informatika Untar",
    version="1.0.0")

# ------------------------------------------------------------- pembatas laju
#
# Endpoint prediksi terbuka tanpa autentikasi — memang disengaja, halaman
# publik memanggilnya tanpa token. Yang perlu ditahan bukan permintaannya,
# melainkan pengulangannya: tanpa pembatas, satu klien dapat menahan seluruh
# kolam koneksi dan membuat login admin maupun siklus penjadwal ikut tertolak.
#
# Batas dihitung per alamat IP. Di belakang Nginx atau Cloudflare, penahanan
# di lapisan itu lebih efektif karena banjir berhenti sebelum menyentuh proses
# Python; pembatas di sini adalah lapis dalam, bukan penggantinya.
# Satu objek Limiter dipakai bersama, bukan satu per berkas: slowapi mencari
# pembatas di app.state.limiter, dan dekorator @batas_masuk() di controller
# mendaftar pada objek milik keamanan. Kalau di sini dibuat objek kedua, batas
# ketat login tidak akan pernah berlaku. Batas umum maupun batas login diatur
# lewat .env; lihat keamanan.BATAS_UMUM dan keamanan.BATAS_MASUK.
app.state.limiter = keamanan.limiter
app.add_middleware(SlowAPIMiddleware)


@app.exception_handler(RateLimitExceeded)
def batas_terlampaui(permintaan: Request, galat: RateLimitExceeded):
    """Menjawab 429 dengan kalimat Indonesia, sesuai tanggapan galat lainnya."""
    return JSONResponse(
        status_code=429,
        content={"detail": "Terlalu banyak permintaan. Coba lagi beberapa saat."})

# Saat pengembangan, React berjalan di porta 5173 sedangkan API di 8000.
# Setelah di-build dan disajikan FastAPI, asalnya sama sehingga CORS tidak
# lagi terpakai.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

for router in SEMUA_ROUTER:
    app.include_router(router)


@app.on_event("startup")
def saat_mulai():
    """Muat kesepuluh model sekali saat start, bukan tiap permintaan.

    Menutup butir g pada catatan proyek: tanpa ini, sepuluh berkas RandomForest
    berukuran rata-rata 39 MB akan dibaca ulang setiap siklus.
    """
    md.periksa_versi_sesi()
    for kode in KODE_SEL:
        md.muat_model(kode)
    print(f"[api] {len(KODE_SEL)} model dimuat ke memori")
    bd.buka_kolam()
    print(f"[api] kolam koneksi siap (maks {bd.MAKS_KOLAM})")


@app.on_event("shutdown")
def saat_berhenti():
    """Menutup kolam koneksi supaya koneksi tidak tertinggal di PostgreSQL."""
    bd.tutup_kolam()


@app.get("/api/sehat", tags=["Sistem"])
def sehat():
    """Pemeriksaan kesehatan layanan (health check)."""
    return {"status": "sehat"}


# --- penyajian antarmuka React, bila sudah di-build --------------------------
DIST = AKAR / "antarmuka" / "dist"

if not DIST.is_dir():
    # Antarmuka belum di-build. Alamat akar dialihkan ke dokumentasi endpoint
    # supaya tidak tampak seperti galat.
    @app.get("/", include_in_schema=False)
    def akar_belum_dibangun():
        """Mengalihkan alamat akar ke dokumentasi API selama antarmuka belum di-build."""
        return RedirectResponse("/docs")

if DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{jalur:path}", include_in_schema=False)
    def antarmuka(jalur: str):
        """Seluruh jalur non-API dikembalikan ke index.html.

        React Router menangani penentuan halaman di sisi peramban, sehingga
        menyegarkan halaman di alamat mana pun tetap bekerja.
        """
        berkas = DIST / jalur
        if jalur and berkas.is_file():
            return FileResponse(berkas)
        return FileResponse(DIST / "index.html")
