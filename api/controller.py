"""Enam controller — lapisan Kendali pada Class Diagram (Gambar 4b).

Satu APIRouter per kelas controller: Autentikasi, Prediksi, Visualisasi,
Monitoring, Riwayat, Informasi. Controller hanya menerjemahkan permintaan HTTP
menjadi panggilan layanan; tidak ada logika di sini.
"""
import json
import sys
import traceback
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import basis_data as bd                                   # noqa: E402
from api import keamanan, layanan, skema                  # noqa: E402
from konfigurasi import (AMBANG_KATEGORI, BAKU_MUTU_1_JAM,  # noqa: E402
                         BATAS_KEMUTAKHIRAN_JAM, FOLDER_MODEL, VERSI_MODEL)


def sambungan():
    """Satu koneksi basis data per permintaan, dipinjam dari kolam.

    Memakai kolam, bukan psycopg.connect() baru tiap permintaan: lihat komentar
    MAKS_KOLAM di basis_data.py untuk biaya dan batas yang mendasarinya.
    """
    with bd.koneksi_kolam() as s:
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


# Batas login lebih ketat daripada batas umum. bcrypt sengaja lambat, jadi
# setiap percobaan memakan CPU server: membanjiri /login bukan hanya peluang
# menerka kata sandi, tetapi sekaligus jalur menghabiskan sumber daya. Batasnya
# dibaca dari keamanan.BATAS_MASUK lewat limiter yang sama.
@autentikasi.post("/login", response_model=skema.Token)
@keamanan.batas_masuk()
def masuk(request: Request, permintaan: skema.PermintaanMasuk,
          s=Depends(sambungan)):
    """Endpoint login: memverifikasi username dan kata sandi, lalu menerbitkan token akses."""
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
    """Daftar kesepuluh sel grid beserta koordinat dan karakteristiknya."""
    return l_lokasi.daftar(s)


# Nama tampilan, satuan, dan kolom model tiap variabel. SO2 selalu dipakai
# (nilai historisnya adalah dasar prediksi); variabel meteorologi hanya yang
# lolos seleksi mutual information pada sel yang bersangkutan.
_VARIABEL = [
    ("so2", "Konsentrasi sulfur dioksida", "µg/m³"),
    ("temperature_2m", "Suhu udara pada 2 m", "°C"),
    ("relative_humidity_2m", "Kelembapan relatif pada 2 m", "%"),
    ("dew_point_2m", "Titik embun pada 2 m", "°C"),
    ("precipitation", "Curah hujan", "mm"),
    ("surface_pressure", "Tekanan permukaan", "hPa"),
    ("cloud_cover", "Tutupan awan total", "%"),
    ("wind_speed_10m", "Kecepatan angin pada 10 m", "m/s"),
    ("wind_direction_10m", "Arah angin pada 10 m", "derajat"),
]


def _variabel_terpilih():
    """Variabel masukan yang benar-benar dipakai, berikut sel yang memakainya."""
    berkas = FOLDER_MODEL / "metadata_model.json"
    meta = json.loads(berkas.read_text(encoding="utf-8"))
    sel_semua = sorted(meta)
    hasil = []
    for kolom, nama, satuan in _VARIABEL:
        if kolom == "so2":
            sel = sel_semua
        else:
            sel = [k for k in sel_semua if kolom in meta[k]["variabel_terpilih"]]
        if sel:
            hasil.append({"nama": nama, "satuan": satuan, "sel": sel})
    return hasil


@informasi.get("/tentang")
def tentang():
    """Informasi umum aplikasi: sumber data, baku mutu, ambang kategori, dan variabel model."""
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
        "variabel": _variabel_terpilih(),
        "peneliti": {
            "nama": "Jovandi Todana", "nim": "535230027",
            "program_studi": "Teknik Informatika", "peminatan": "Data Science",
            "institusi": "Fakultas Teknologi Informasi, Universitas Tarumanagara"},
        "pembimbing": [
            {"peran": "Dosen pembimbing utama",
             "nama": "Teny Handhayani, S.Kom., M.Kom., Ph.D."},
            {"peran": "Dosen pembimbing pendamping",
             "nama": "Henoch Juli Christanto, S.Kom., M.Kom."}],
    }


@informasi.get("/faq")
def faq():
    """Daftar pertanyaan yang sering diajukan beserta jawabannya."""
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
    """Status kemutakhiran data dan sinkronisasi terakhir tiap sel grid, untuk Modul Monitoring."""
    return l_sinkron.status(s)


@monitoring.get("/siklus")
def siklus(batas: int = Query(20, ge=1, le=200), s=Depends(sambungan), pengguna=admin):
    """Riwayat siklus sinkronisasi terbaru."""
    return l_sinkron.siklus_terakhir(s, batas)


@monitoring.get("/anomali")
def anomali(batas: int = Query(200, ge=1, le=1000),
            s=Depends(sambungan), pengguna=admin):
    """Daftar pengamatan yang berstatus anomali atau dikecualikan."""
    return l_sinkron.anomali(s, batas)


@monitoring.get("/koreksi")
def riwayat_koreksi(batas: int = Query(100, ge=1, le=500),
                    s=Depends(sambungan), pengguna=admin):
    """Jejak audit koreksi yang pernah dilakukan admin atas data pengamatan."""
    return l_sinkron.riwayat_koreksi(s, batas)


@monitoring.post("/koreksi")
def catat_koreksi(permintaan: skema.PermintaanKoreksi,
                  s=Depends(sambungan), pengguna=admin):
    """Mencatat tindakan admin (tandai, kecualikan, pulihkan, ubah nilai) atas satu pengamatan."""
    try:
        return l_sinkron.koreksi(s, pengguna["id_pengguna"], permintaan)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# Galat teknis yang tidak berarti apa pun bagi admin, dipetakan ke kalimat yang
# menyebut apa yang terjadi dan apa langkah berikutnya. "InFailedSqlTransaction:
# current transaction is aborted" khususnya hanyalah puing: ia muncul sesudah
# ada perintah SQL lain yang ditolak, jadi yang terbaca admin bukan sebabnya.
PESAN_GALAT_SINKRONISASI = {
    "InFailedSqlTransaction":
        "Penyimpanan ditolak basis data, sehingga sisa siklus dibatalkan. "
        "Galat aslinya tercatat di log server; riwayat sinkronisasi mungkin "
        "tidak lengkap untuk siklus ini.",
    "OperationalError":
        "Sambungan ke basis data terputus saat sinkronisasi berjalan. "
        "Periksa apakah layanan PostgreSQL masih hidup, lalu coba lagi.",
    "UniqueViolation":
        "Basis data menolak baris ganda saat mencatat hasil sinkronisasi. "
        "Ini kekeliruan aplikasi, bukan kesalahan masukan — laporkan beserta "
        "jam percobaan ini.",
    "PenolakanAPI":
        "Sumber data Open-Meteo menolak permintaan. Biasanya karena batas "
        "kuota atau jaringan; tunggu beberapa menit lalu coba lagi.",
}


@monitoring.post("/sinkronisasi")
def sinkronisasi_manual(s=Depends(sambungan), pengguna=admin):
    """Memicu sinkronisasi ulang; dijanjikan naskah bagi admin."""
    try:
        return l_sinkron.jalankan_manual(s, pengguna["id_pengguna"])
    except Exception as e:                                  # noqa: BLE001
        nama = type(e).__name__
        # Pesan teknis tetap masuk log server, tempatnya memang di sana.
        traceback.print_exc()
        ramah = PESAN_GALAT_SINKRONISASI.get(nama)
        if ramah:
            detail = ramah
        else:
            # Jenis galat yang belum dikenal: sebutkan apa adanya, tetapi tetap
            # dengan kalimat pembuka yang menjelaskan tahap mana yang gagal.
            detail = (f"Sinkronisasi dihentikan oleh galat tak terduga "
                      f"({nama}): {e}")
        raise HTTPException(status_code=502, detail=detail)


# ================================================================ ControllerRiwayat
riwayat = APIRouter(prefix="/api/riwayat", tags=["Riwayat Prediksi"])


@riwayat.get("/prediksi")
def riwayat_prediksi(kode_sel: str | None = None,
                     batas: int = Query(200, ge=1, le=2000),
                     hanya_terisi: bool = False,
                     s=Depends(sambungan), pengguna=admin):
    """Riwayat prediksi beserta nilai aktualnya, dapat disaring per sel."""
    return l_riwayat.riwayat(s, kode_sel.upper() if kode_sel else None,
                             batas, hanya_terisi)


@riwayat.get("/ketelitian", response_model=skema.Ketelitian)
def ketelitian(s=Depends(sambungan), pengguna=admin):
    """Ukuran ketelitian operasional model (MAE, RMSE, skill score) dibanding pembanding."""
    return l_riwayat.ketelitian(s)


SEMUA_ROUTER = [autentikasi, prediksi, visualisasi, informasi, monitoring, riwayat]
