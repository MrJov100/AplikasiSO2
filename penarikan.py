"""Penarikan data dari Open-Meteo untuk satu sel grid.

Parameter permintaan dijaga sama persis dengan penarikan data latih: koordinat
permintaan (bukan koordinat kisi), elevasi, satuan m/detik untuk angin,
domains=cams_global untuk SO2, dan models=ecmwf_ifs untuk meteorologi. Apa pun
yang berbeda akan menghasilkan deret yang tidak setara dengan data latih.
"""
import time
from datetime import timedelta

import pandas as pd
import requests

from konfigurasi import HARI_MUNDUR, ZONA

API_SO2 = "https://air-quality-api.open-meteo.com/v1/air-quality"
API_METEO = "https://archive-api.open-meteo.com/v1/archive"
MODEL_METEO = "ecmwf_ifs"
DOMAIN_SO2 = "cams_global"

VAR_METEO = ["temperature_2m", "relative_humidity_2m", "dew_point_2m", "precipitation",
             "surface_pressure", "cloud_cover", "wind_speed_10m", "wind_direction_10m"]
SATUAN = {"wind_speed_unit": "ms", "temperature_unit": "celsius",
          "precipitation_unit": "mm"}

BATAS_WAKTU_API = 30
PERCOBAAN = 3
JEDA_AWAL = 2.0

# Nama kolom Open-Meteo -> nama kolom tabel PENGAMATAN.
KE_KOLOM_DB = {
    "so2": "so2",
    "temperature_2m": "suhu",
    "relative_humidity_2m": "kelembapan",
    "dew_point_2m": "titik_embun",
    "precipitation": "curah_hujan",
    "surface_pressure": "tekanan_permukaan",
    "cloud_cover": "tutupan_awan",
    "wind_speed_10m": "kecepatan_angin",
    "wind_direction_10m": "arah_angin",
}


class GalatPenarikan(RuntimeError):
    """Penarikan Open-Meteo gagal. Teks galatnya ditulis untuk dibaca admin.

    Pesan ini disimpan apa adanya di sinkronisasi_lokasi.pesan_galat
    (varchar 255) dan ditampilkan di halaman Monitoring, jadi harus pendek dan
    menyebut sumber mana yang gagal (data SO2 atau data cuaca).
    """


class PenolakanAPI(GalatPenarikan):
    """Open-Meteo menjawab 4xx: parameter permintaan ditolak.

    Tetap dicoba ulang seperti galat lain. Pada 26 dan 30 Oktober 2026 pukul
    07.10 WIB (00.10 UTC, saat arsip berganti tanggal) Open-Meteo menjawab
    {"error": true, "reason": "Something went wrong."}. Kode lama menganggap
    setiap badan JSON berisi "error" sebagai penolakan permanen dan tidak
    mengulangnya, padahal itu galat server sesaat. Penarikan manual 29 menit
    kemudian berhasil. Sejak itu tidak ada lagi kegagalan yang dikecualikan
    dari pengulangan.
    """


def _ringkas(teks, panjang=80):
    """Potong teks dari sumber luar agar pesan admin tetap muat 255 karakter."""
    teks = " ".join(str(teks or "").split())
    return teks if len(teks) <= panjang else teks[:panjang - 3] + "..."


def _galat_tanggapan(r, isi, sumber):
    """Ubah tanggapan Open-Meteo yang tidak berhasil menjadi galat untuk admin."""
    kode = r.status_code
    alasan = _ringkas(isi.get("reason")) if isinstance(isi, dict) else ""
    if isi is None:
        return GalatPenarikan(
            f"Open-Meteo mengirim jawaban yang tidak dapat dibaca saat menarik "
            f"{sumber} (HTTP {kode}).")
    if kode == 429:
        return GalatPenarikan(
            f"Kuota permintaan Open-Meteo habis saat menarik {sumber} (HTTP 429).")
    if 400 <= kode < 500:
        if "out of allowed range" in (alasan or ""):
            return PenolakanAPI(
                f"Arsip Open-Meteo belum menyediakan {sumber} untuk tanggal yang "
                f"diminta (HTTP {kode}).")
        return PenolakanAPI(
            f"Open-Meteo menolak permintaan {sumber} (HTTP {kode}): {alasan}.")
    # 5xx, atau 200 yang berisi {"error": true}.
    return GalatPenarikan(
        f"Server Open-Meteo sedang bermasalah saat menarik {sumber} "
        f"(HTTP {kode}{': ' + alasan if alasan else ''}). Gangguan di pihak "
        f"Open-Meteo, bukan aplikasi.")


def _minta(url, params, sumber):
    """Kirim permintaan dengan percobaan ulang dan jeda yang menggandakan diri.

    Kegagalan apa pun diulang, sampai PERCOBAAN kali (jeda 2 lalu 4 detik).
    Sesudah itu galat dilempar, dan penarikan ulang 5 menit kemudian
    ditangani segarkan_pengamatan.jalankan_siklus().
    """
    jeda = JEDA_AWAL
    galat = None
    for percobaan in range(1, PERCOBAAN + 1):
        try:
            r = requests.get(url, params=params, timeout=BATAS_WAKTU_API)
        except requests.Timeout:
            galat = GalatPenarikan(
                f"Open-Meteo tidak menjawab dalam {BATAS_WAKTU_API} detik saat "
                f"menarik {sumber}.")
        except requests.ConnectionError:
            galat = GalatPenarikan(
                f"Tidak dapat terhubung ke Open-Meteo saat menarik {sumber}. "
                f"Jaringan server terputus atau Open-Meteo tidak dapat diakses.")
        except requests.RequestException as e:
            galat = GalatPenarikan(
                f"Permintaan {sumber} ke Open-Meteo gagal: "
                f"{_ringkas(type(e).__name__ + ': ' + str(e))}.")
        else:
            try:
                isi = r.json()
            except ValueError:
                isi = None
            if r.ok and isinstance(isi, dict) and not isi.get("error"):
                return isi
            galat = _galat_tanggapan(r, isi, sumber)
        if percobaan < PERCOBAAN:
            time.sleep(jeda)
            jeda *= 2
    raise galat


def jam_sekarang():
    """Jam berjalan waktu Jakarta, dibulatkan ke bawah, tanpa zona waktu."""
    return pd.Timestamp.now(tz=ZONA).tz_localize(None).floor("h")


def tarik_sel(lintang, bujur, elevasi, hari_mundur=HARI_MUNDUR, batas_waktu=None):
    """Tarik SO2 dan delapan variabel meteorologi untuk satu titik.

    Return: (tabel, koordinat_kisi)
      tabel  DataFrame berindeks waktu, kolom bernama seperti tabel PENGAMATAN,
             SO2 negatif sudah dipangkas ke nol dengan aslinya di so2_mentah,
             arah angin 360 sudah dinormalkan menjadi 0.
      koordinat_kisi  (lintang, bujur) yang dikembalikan Air Quality API.
    """
    if batas_waktu is None:
        batas_waktu = jam_sekarang()

    isi = _minta(API_SO2, {
        "latitude": lintang, "longitude": bujur, "elevation": elevasi,
        "hourly": "sulphur_dioxide", "domains": DOMAIN_SO2,
        "past_days": hari_mundur, "forecast_days": 1, "timezone": ZONA},
        "data SO2")
    kisi = (isi.get("latitude"), isi.get("longitude"))
    so2 = pd.DataFrame({
        "time": pd.to_datetime(isi["hourly"]["time"]),
        "so2": pd.to_numeric(isi["hourly"]["sulphur_dioxide"], errors="coerce"),
    }).dropna(subset=["so2"])

    # Arsip Open-Meteo membuka tanggal baru mengikuti UTC, sedangkan Jakarta
    # (UTC+7) berganti tanggal 7 jam lebih awal. Maka jendela arsip diminta
    # dalam hari UTC (timezone="UTC"), lalu labelnya dikonversi ke Jakarta di
    # pandas. Jangan ganti ke tanggal Jakarta:
    #   - end_date bisa melampaui batas arsip pada 00.00-07.00 WIB, sehingga
    #     seluruh permintaan ditolak ("end_date is out of allowed range");
    #   - jika hanya end_date yang dipangkas ke UTC tetapi label tetap Jakarta,
    #     jam 00.00-06.00 WIB tidak terambil dan prediksi hari itu hilang.
    # Parameter timezone hanya mengubah label jam, bukan nilainya, jadi
    # kesetaraan dengan data latih terjaga. Penggabungan dengan data SO2
    # (berlabel Jakarta) dilakukan pada label Jakarta yang sama.
    akhir_utc = pd.Timestamp.now(tz="UTC").normalize().tz_localize(None)

    isi = _minta(API_METEO, {
        "latitude": lintang, "longitude": bujur, "elevation": elevasi,
        "start_date": (akhir_utc - timedelta(days=hari_mundur)).strftime("%Y-%m-%d"),
        "end_date": akhir_utc.strftime("%Y-%m-%d"),
        "hourly": ",".join(VAR_METEO), "models": MODEL_METEO,
        "timezone": "UTC", **SATUAN},
        "data cuaca")
    meteo = pd.DataFrame({"time": pd.to_datetime(isi["hourly"]["time"], utc=True)})
    for v in VAR_METEO:
        meteo[v] = pd.to_numeric(isi["hourly"][v], errors="coerce")
    meteo["time"] = meteo["time"].dt.tz_convert(ZONA).dt.tz_localize(None)
    meteo = meteo.dropna(subset=VAR_METEO)

    tabel = so2.merge(meteo, on="time", how="inner", validate="one_to_one")

    # Baris melewati jam berjalan dibuang: kedua endpoint mengembalikan nilai
    # untuk jam yang belum terjadi, dan nilai seperti itu prakiraan, bukan
    # pengamatan.
    tabel = tabel[tabel["time"] <= batas_waktu].sort_values("time")

    # Pra-pemrosesan yang sama persis dengan Subbab 2.1.5 dan dengan seed.
    tabel["so2_mentah"] = tabel["so2"].where(tabel["so2"] < 0)
    tabel["so2"] = tabel["so2"].clip(lower=0)

    # Kekangan ck_pengamatan_arah_angin menuntut 0 <= arah < 360, sedangkan
    # Open-Meteo mengembalikan 360 untuk utara. Keduanya arah yang sama.
    tabel.loc[tabel["wind_direction_10m"] >= 360, "wind_direction_10m"] = 0

    tabel = tabel.rename(columns=KE_KOLOM_DB).set_index("time")
    kolom = list(KE_KOLOM_DB.values()) + ["so2_mentah"]
    return tabel[kolom], kisi
