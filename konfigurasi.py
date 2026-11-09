"""Konfigurasi aplikasi, dibaca dari berkas .env."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name(".env"))

PG = {
    "host":     os.getenv("PG_HOST", "localhost"),
    "port":     int(os.getenv("PG_PORT", "5432")),
    "dbname":   os.getenv("PG_DB", "so2_jabodetabek"),
    "user":     os.getenv("PG_USER", "so2_app"),
    "password": os.getenv("PG_PASSWORD", ""),
}

FOLDER_MODEL = Path(os.getenv("FOLDER_MODEL", ""))
FOLDER_MODEL_ASLI = Path(os.getenv("FOLDER_MODEL_ASLI", ""))

VERSI_MODEL = os.getenv("VERSI_MODEL", "stacking-s2-20260731")

# Menit keberangkatan penjadwal tiap jam. Bukan menit nol: arsip Open-Meteo
# perlu waktu memuat jam yang baru lewat.
MENIT_JADWAL = int(os.getenv("MENIT_JADWAL", "10"))

SKENARIO = 2
LAGS = (1, 2, 3)
ZONA = "Asia/Jakarta"
BATAS_KEMUTAKHIRAN_JAM = 1

# Tabel 2.1 naskah. Baku mutu satu jam PP 22/2021 = 150 ug/m3.
AMBANG_KATEGORI = [(75.0, "Baik"), (150.0, "Sedang"), (300.0, "Buruk")]
KATEGORI_TERATAS = "Sangat Buruk"
BAKU_MUTU_1_JAM = 150.0

KODE_SEL = [f"G{i:02d}" for i in range(1, 11)]

# ------------------------------------- Modul MonEv SO2 (Monitoring dan Evaluasi)
# Perubahan = prediksi satu jam ke depan dikurangi konsentrasi teramati terakhir
# (potret sezaman; lihat MonevRepository di api/repositori.py).
#
# Ambang peringatan 8 ug/m3 = persentil ke-95 kenaikan SO2 antara dua jam
# berurutan: 8,0 pada data historis (naskah Bab I) dan 7,9 pada 40 hari data
# operasional (29 Sep - 9 Nov 2026). Kenaikan sebesar itu termasuk 5% kenaikan
# terbesar, sekaligus kira-kira lima kali galat rata-rata model.
#
# Pita stabil 1,5 ug/m3 = MAE operasional (naskah Bab IV: 1,5330). Perubahan yang
# lebih kecil dari galat rata-rata model tidak dapat dibedakan dari galat itu
# sendiri, sehingga dinyatakan "Stabil".
AMBANG_PERINGATAN_KENAIKAN = 8.0
PITA_STABIL = 1.5
# Jendela dihitung mundur dari jam target prediksi TERBARU yang tersimpan, bukan
# dari jam saat ini; alasannya di LayananMonev.ringkasan (api/layanan.py).
HARI_EVALUASI_MONEV = (7, 30)     # dua jendela evaluasi yang ditampilkan berdampingan
HARI_RIWAYAT_PERINGATAN = 7       # rentang daftar riwayat peringatan

HARI_MUNDUR = 3          # cukup menjangkau t-1..t-3 dengan margin, dan sekaligus
                         # mencakup dua sampai tiga batas run 00z/12z

# Koordinat PERMINTAAN dan elevasi, sama persis dengan penarikan data latih.
# Bukan koordinat kisi yang dikembalikan API: memakai koordinat kisi bisa
# membuat permintaan mendarat di sel yang berbeda.
SEL_GRID = {
    "G01": (-5.750, 106.550,   0), "G02": (-5.745, 106.613,   0),
    "G03": (-6.055, 106.395,   3), "G04": (-6.105, 106.880,   4),
    "G05": (-6.050, 107.060,   3), "G06": (-6.340, 106.470,  60),
    "G07": (-6.400, 106.820,  92), "G08": (-6.260, 107.150,  18),
    "G09": (-6.680, 106.552, 786), "G10": (-6.670, 106.870, 587),
}

# Pemetaan nama kolom basis data ke nama kolom yang dipakai berkas model.
# Nama fitur pada model berbentuk "<kolom>_t<lag>", jadi nama di sebelah kanan
# harus sama persis dengan nama kolom saat pelatihan.
KOLOM_DB_KE_MODEL = {
    "so2":               "so2",
    "suhu":              "temperature_2m",
    "kelembapan":        "relative_humidity_2m",
    "titik_embun":       "dew_point_2m",
    "curah_hujan":       "precipitation",
    "tekanan_permukaan": "surface_pressure",
    "tutupan_awan":      "cloud_cover",
    "kecepatan_angin":   "wind_speed_10m",
    "arah_angin":        "wind_direction_10m",
}
