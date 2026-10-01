"""Enam controller — lapisan Kendali pada Class Diagram (Gambar 4b).

Satu APIRouter per kelas controller: Autentikasi, Prediksi, Visualisasi,
Monitoring, Riwayat, Informasi. Controller hanya menerjemahkan permintaan HTTP
menjadi panggilan layanan; tidak ada logika di sini.
"""
import sys
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import basis_data as bd                                   # noqa: E402
from api import keamanan, layanan, skema                  # noqa: E402
from konfigurasi import (AMBANG_KATEGORI, BAKU_MUTU_1_JAM,  # noqa: E402
                         BATAS_KEMUTAKHIRAN_JAM, VERSI_MODEL)


def sambungan():
    """Satu koneksi basis data per permintaan."""
    with bd.koneksi() as s:
        yield s


admin = Depends(keamanan.pengguna_aktif)

l_lokasi = layanan.LayananLokasi()
l_auth = layanan.LayananAutentikasi()
l_prediksi = layanan.LayananPrediksi()
l_visual = layanan.LayananVisualisasi()
l_sinkron = layanan.LayananSinkronisasi()
l_riwayat = layanan.LayananRiwayat()


# ============================================================ ControllerAutentikasi
autentikasi = APIRouter(prefix="/api/auth", tags=["Autentikasi"])


@autentikasi.post("/login", response_model=skema.Token)
def masuk(permintaan: skema.PermintaanMasuk, s=Depends(sambungan)):
    p = l_auth.masuk(s, permintaan.username, permintaan.kata_sandi)
    if not p:
        raise HTTPException(status_code=401,
                            detail="Username atau kata sandi salah.")
    return {"akses_token": keamanan.buat_token(p), "jenis_token": "bearer",
            "nama_lengkap": p["nama_lengkap"], "peran": p["peran"]}


@autentikasi.get("/saya", response_model=skema.ProfilPengguna)
def saya(s=Depends(sambungan), pengguna=admin):
    """Rincian profil admin yang sedang masuk, untuk pop-up Profil Admin."""
    try:
        return l_auth.profil(s, pengguna["id_pengguna"])
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


@autentikasi.patch("/profil", response_model=skema.ProfilPengguna)
def ubah_profil(permintaan: skema.PermintaanUbahNama,
                s=Depends(sambungan), pengguna=admin):
    """Admin mengganti nama lengkapnya sendiri."""
    try:
        return l_auth.ubah_nama(s, pengguna["id_pengguna"],
                                permintaan.nama_lengkap)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@autentikasi.patch("/kata-sandi")
def ubah_kata_sandi(permintaan: skema.PermintaanUbahKataSandi,
                    s=Depends(sambungan), pengguna=admin):
    """Admin mengganti kata sandinya sendiri; kata sandi lama wajib benar."""
    try:
        l_auth.ubah_kata_sandi(s, pengguna["id_pengguna"],
                               permintaan.kata_sandi_lama,
                               permintaan.kata_sandi_baru)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"pesan": "Kata sandi berhasil diganti."}


# =============================================================== ControllerPrediksi
prediksi = APIRouter(prefix="/api/prediksi", tags=["Prediksi"])


@prediksi.get("/terkini")
def semua_terkini(s=Depends(sambungan)):
    """Prediksi terbaru kesepuluh sel grid, untuk Halaman Beranda."""
    return l_prediksi.semua_terkini(s)


@prediksi.get("/terkini/{kode_sel}", response_model=skema.PrediksiTerkini)
def terkini(kode_sel: str, s=Depends(sambungan)):
    """Prediksi terbaru satu sel grid, untuk Modul Prediksi SO2."""
    return l_prediksi.terkini(s, kode_sel.upper())


# ============================================================ ControllerVisualisasi
visualisasi = APIRouter(prefix="/api/visualisasi", tags=["Visualisasi"])


@visualisasi.get("/riwayat/{kode_sel}")
def riwayat_pengamatan(kode_sel: str,
                       jam: int = Query(168, ge=6, le=2160),
                       s=Depends(sambungan)):
    """Deret SO2 per jam beserta garis acuan baku mutu."""
    return l_visual.riwayat(s, kode_sel.upper(), jam)


# ============================================================== ControllerInformasi
informasi = APIRouter(prefix="/api/informasi", tags=["Informasi"])


@informasi.get("/lokasi", response_model=list[skema.Lokasi])
def daftar_lokasi(s=Depends(sambungan)):
    return l_lokasi.daftar(s)


@informasi.get("/tentang")
def tentang():
    return {
        "nama": "Prediksi Konsentrasi SO₂ Jabodetabek",
        "keterangan": (
            "Aplikasi ini memperkirakan konsentrasi sulfur dioksida satu jam ke "
            "depan pada sepuluh sel grid Jabodetabek memakai stacking ensemble "
            "XGBoost dan Random Forest dengan meta-learner Ridge."),
        "sumber_data": (
            "Open-Meteo. Konsentrasi SO₂ dari CAMS Global; variabel "
            "meteorologi dari ECMWF IFS resolusi 9 km. Nilainya adalah estimasi "
            "keluaran model numerik, bukan pengukuran stasiun pemantauan."),
        "baku_mutu_satu_jam": BAKU_MUTU_1_JAM,
        "satuan": "µg/m³",
        "ambang_kategori": [{"batas_atas": b, "nama": n} for b, n in AMBANG_KATEGORI]
                           + [{"batas_atas": None, "nama": "Sangat Buruk"}],
        "versi_model": VERSI_MODEL,
        "batas_kemutakhiran_jam": BATAS_KEMUTAKHIRAN_JAM,
        "variabel": [
            {"nama": "Konsentrasi sulfur dioksida", "satuan": "µg/m³"},
            {"nama": "Suhu udara pada 2 m", "satuan": "°C"},
            {"nama": "Kelembapan relatif pada 2 m", "satuan": "%"},
            {"nama": "Titik embun pada 2 m", "satuan": "°C"},
            {"nama": "Curah hujan", "satuan": "mm"},
            {"nama": "Tekanan permukaan", "satuan": "hPa"},
            {"nama": "Tutupan awan total", "satuan": "%"},
            {"nama": "Kecepatan angin pada 10 m", "satuan": "m/s"},
            {"nama": "Arah angin pada 10 m", "satuan": "derajat"}],
    }


@informasi.get("/faq")
def faq():
    return [
        {"tanya": "Dari mana datanya?",
         "jawab": "Open-Meteo. Konsentrasi SO₂ berasal dari CAMS Global dan "
                  "variabel meteorologi dari ECMWF IFS 9 km. Keduanya estimasi "
                  "keluaran model numerik, bukan hasil pengukuran alat di lapangan."},
        {"tanya": "Seberapa jauh ke depan prediksinya?",
         "jawab": "Satu jam. Sistem membaca tiga pengamatan terakhir, lalu "
                  "memperkirakan konsentrasi satu jam sesudahnya."},
        {"tanya": "Apa arti kategorinya?",
         "jawab": "Baik 0–75, Sedang 75–150, Buruk 150–300, dan "
                  "Sangat Buruk di atas 300 µg/m³. Baku mutu satu jam "
                  "menurut PP 22/2021 adalah 150 µg/m³. Ini bukan ISPU "
                  "dan bukan European AQI."},
        {"tanya": "Mengapa kadang tertulis data belum mutakhir?",
         "jawab": "Arsip sumber kadang terlambat memuat jam terakhir. Bila "
                  "ketertinggalannya lebih dari satu jam, sistem menahan diri "
                  "daripada menampilkan prediksi untuk jam yang sudah lewat."},
        {"tanya": "Mengapa hanya sepuluh titik?",
         "jawab": "Kesepuluh sel grid dipilih mewakili keragaman Jabodetabek: "
                  "perairan, pesisir, kawasan industri, urban padat, dan dataran "
                  "tinggi. Tiap sel memiliki model tersendiri."},
        {"tanya": "Apakah nilainya bisa dipakai untuk keperluan resmi?",
         "jawab": "Tidak. Aplikasi ini hasil penelitian skripsi dan ditujukan "
                  "sebagai informasi awal bagi masyarakat, bukan pengganti data "
                  "resmi instansi pemantau kualitas udara."},
    ]


# ============================================================= ControllerMonitoring
monitoring = APIRouter(prefix="/api/monitoring", tags=["Monitoring"])


@monitoring.get("/status", response_model=list[skema.StatusSel])
def status_data(s=Depends(sambungan), pengguna=admin):
    return l_sinkron.status(s)


@monitoring.get("/siklus")
def siklus(batas: int = Query(20, ge=1, le=200), s=Depends(sambungan), pengguna=admin):
    return l_sinkron.siklus_terakhir(s, batas)


@monitoring.get("/anomali")
def anomali(batas: int = Query(200, ge=1, le=1000),
            s=Depends(sambungan), pengguna=admin):
    return l_sinkron.anomali(s, batas)


@monitoring.get("/koreksi")
def riwayat_koreksi(batas: int = Query(100, ge=1, le=500),
                    s=Depends(sambungan), pengguna=admin):
    return l_sinkron.riwayat_koreksi(s, batas)


@monitoring.post("/koreksi")
def catat_koreksi(permintaan: skema.PermintaanKoreksi,
                  s=Depends(sambungan), pengguna=admin):
    try:
        return l_sinkron.koreksi(s, pengguna["id_pengguna"], permintaan)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@monitoring.post("/sinkronisasi")
def sinkronisasi_manual(s=Depends(sambungan), pengguna=admin):
    """Memicu sinkronisasi ulang; dijanjikan naskah bagi admin."""
    try:
        return l_sinkron.jalankan_manual(s, pengguna["id_pengguna"])
    except Exception as e:                                  # noqa: BLE001
        raise HTTPException(status_code=502,
                            detail=f"Sinkronisasi gagal: {type(e).__name__}: {e}")


# ================================================================ ControllerRiwayat
riwayat = APIRouter(prefix="/api/riwayat", tags=["Riwayat Prediksi"])


@riwayat.get("/prediksi")
def riwayat_prediksi(kode_sel: str | None = None,
                     batas: int = Query(200, ge=1, le=2000),
                     hanya_terisi: bool = False,
                     s=Depends(sambungan), pengguna=admin):
    return l_riwayat.riwayat(s, kode_sel.upper() if kode_sel else None,
                             batas, hanya_terisi)


@riwayat.get("/ketelitian", response_model=skema.Ketelitian)
def ketelitian(s=Depends(sambungan), pengguna=admin):
    return l_riwayat.ketelitian(s)


SEMUA_ROUTER = [autentikasi, prediksi, visualisasi, informasi, monitoring, riwayat]
