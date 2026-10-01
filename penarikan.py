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


class PenolakanAPI(RuntimeError):
    """Open-Meteo menolak permintaannya sendiri — bukan galat sesaat.

    Open-Meteo mengembalikan penolakan parameter sebagai badan JSON
    {"error": true, "reason": ...}, BUKAN sebagai status 4xx. Sebelum
    1 Oktober 2026 penolakan itu dilempar sebagai RuntimeError biasa sehingga
    tertangkap cabang pengulangan: satu permintaan yang pasti ditolak tetap
    dicoba tiga kali dengan jeda menggandakan, memboroskan ±9 detik per sel dan
    menyembunyikan sebab aslinya di balik "Gagal setelah 3 percobaan".
    Kelas sendiri membuatnya lolos tanpa diulang, seperti niat docstring.
    """


def _minta(url, params):
    """Kirim permintaan dengan percobaan ulang dan jeda yang menggandakan diri.

    Satu kegagalan sesaat tidak boleh menghapus prediksi satu jam. Yang diulang
    hanya galat jaringan dan 5xx. Galat 4xx dan penolakan parameter dari
    Open-Meteo tidak diulang karena permintaannya memang salah, dan mengulangnya
    hanya menunda kabar buruk.
    """
    jeda = JEDA_AWAL
    galat_terakhir = None
    for percobaan in range(1, PERCOBAAN + 1):
        try:
            r = requests.get(url, params=params, timeout=BATAS_WAKTU_API)
            try:
                isi = r.json()
            except ValueError:
                r.raise_for_status()
                raise RuntimeError(f"Tanggapan dari {url} bukan JSON")
            if isinstance(isi, dict) and isi.get("error"):
                raise PenolakanAPI(f"Open-Meteo menolak: {isi.get('reason')}")
            if 400 <= r.status_code < 500:
                r.raise_for_status()
            r.raise_for_status()
            return isi
        except PenolakanAPI:
            raise                       # penolakan tetap: jangan diulang
        except requests.HTTPError as e:
            if e.response is not None and 400 <= e.response.status_code < 500:
                raise
            galat_terakhir = e
        except (requests.RequestException, RuntimeError) as e:
            galat_terakhir = e
        if percobaan < PERCOBAAN:
            time.sleep(jeda)
            jeda *= 2
    raise RuntimeError(f"Gagal setelah {PERCOBAAN} percobaan: {galat_terakhir}")


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
        "past_days": hari_mundur, "forecast_days": 1, "timezone": ZONA})
    kisi = (isi.get("latitude"), isi.get("longitude"))
    so2 = pd.DataFrame({
        "time": pd.to_datetime(isi["hourly"]["time"]),
        "so2": pd.to_numeric(isi["hourly"]["sulphur_dioxide"], errors="coerce"),
    }).dropna(subset=["so2"])

    # JENDELA ARSIP DISUSUN DAN DIMINTA DALAM HARI UTC, BUKAN HARI JAKARTA.
    #
    # Dua kegagalan berurutan lahir dari satu sebab yang sama: arsip Open-Meteo
    # membuka tanggal baru mengikuti UTC, sedangkan Jakarta (UTC+7) sudah
    # berganti tanggal tujuh jam lebih awal.
    #
    # 1. Sampai 30 September 2026 end_date diambil dari tanggal Jakarta. Antara
    #    00.00 dan 07.00 WIB tanggal itu selalu satu hari di depan batas yang
    #    diizinkan arsip, sehingga seluruh permintaan ditolak dengan "Parameter
    #    'end_date' is out of allowed range from 1940-01-01 to ...". Terlihat
    #    1 Oktober 2026 pukul 00.10 WIB, ketika penjadwal pertama kali menyala
    #    melewati tengah malam.
    #
    # 2. Memangkas end_date ke tanggal UTC menghentikan penolakan itu, tetapi
    #    jendelanya masih DILABELI dalam waktu Jakarta. Akibatnya jam WIB
    #    00.00-06.00 tidak pernah ikut diminta: jam-jam itu sudah masuk hari
    #    Jakarta yang baru, padahal masih berada di dalam hari UTC yang
    #    diizinkan (00.00 WIB 1 Okt = 17.00 UTC 30 Sep). Pengamatan berhenti di
    #    23.00 WIB hari sebelumnya, penjaga kemutakhiran menolak, dan enam
    #    prediksi hilang setiap hari. Terlihat pada log 1 Oktober 2026 siklus
    #    28-33: sepuluh sel, 72 baris, "sisip 0" di setiap siklus.
    #
    # Karena itu jendela kini diminta sepenuhnya dalam hari UTC, lalu labelnya
    # dikonversi ke waktu Jakarta di pandas. Parameter timezone hanya mengubah
    # pelabelan dan pengirisan jam, BUKAN nilainya, sehingga kesetaraan dengan
    # data latih tetap terjaga: models, domains, koordinat, elevasi, dan satuan
    # tidak disentuh. Permintaan SO2 tetap memakai past_days/forecast_days
    # dengan label Jakarta; penggabungan di bawah mempertemukan keduanya pada
    # label Jakarta yang sama.
    #
    # Yang tersisa sebagai batas hanyalah jeda penerbitan arsip, sama seperti
    # siang hari. Bila jeda itu melebar, penjaga kemutakhiran pada
    # tentukan_waktu_target tetap menolak membentuk prediksi.
    akhir_utc = pd.Timestamp.now(tz="UTC").normalize().tz_localize(None)

    isi = _minta(API_METEO, {
        "latitude": lintang, "longitude": bujur, "elevation": elevasi,
        "start_date": (akhir_utc - timedelta(days=hari_mundur)).strftime("%Y-%m-%d"),
        "end_date": akhir_utc.strftime("%Y-%m-%d"),
        "hourly": ",".join(VAR_METEO), "models": MODEL_METEO,
        "timezone": "UTC", **SATUAN})
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
