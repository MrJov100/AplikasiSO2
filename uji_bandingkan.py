"""Uji kesetaraan basis data versus Open-Meteo, dengan diagnosa per jam.

Cara membaca hasil: nilai jam yang belum lewat saat data ditarik adalah
prakiraan, lalu diperbarui Open-Meteo. Selisih pada jam-jam terakhir seed
wajar; selisih pada jam lama berarti ada masalah. Mode --diagnosa menunjukkan
batasnya.

    python uji_bandingkan.py --sel G04 --diagnosa
    python uji_bandingkan.py --sel G04 --target "2026-09-28 00:00"
"""
import argparse
import sys
from datetime import timedelta

import numpy as np
import pandas as pd
import requests

import basis_data as bd
import model as md
from konfigurasi import LAGS, ZONA

API_SO2 = "https://air-quality-api.open-meteo.com/v1/air-quality"
API_METEO = "https://archive-api.open-meteo.com/v1/archive"
MODEL_METEO = "ecmwf_ifs"
DOMAIN_SO2 = "cams_global"
VAR_METEO = ["temperature_2m", "relative_humidity_2m", "dew_point_2m", "precipitation",
             "surface_pressure", "cloud_cover", "wind_speed_10m", "wind_direction_10m"]
SATUAN = {"wind_speed_unit": "ms", "temperature_unit": "celsius",
          "precipitation_unit": "mm"}
HARI_MUNDUR = 3

# Koordinat permintaan dan elevasi, sama dengan data latih. Elevasi wajib ikut
# karena memengaruhi penyesuaian suhu dan tekanan.
SEL_GRID = {
    "G01": (-5.750, 106.550,   0), "G02": (-5.745, 106.613,   0),
    "G03": (-6.055, 106.395,   3), "G04": (-6.105, 106.880,   4),
    "G05": (-6.050, 107.060,   3), "G06": (-6.340, 106.470,  60),
    "G07": (-6.400, 106.820,  92), "G08": (-6.260, 107.150,  18),
    "G09": (-6.680, 106.552, 786), "G10": (-6.670, 106.870, 587),
}


def _minta(url, params):
    """Permintaan GET ke Open-Meteo yang mengembalikan JSON, atau galat bila tanggapan bukan JSON."""
    r = requests.get(url, params=params, timeout=30)
    try:
        isi = r.json()
    except ValueError:
        r.raise_for_status()
        raise RuntimeError(f"Tanggapan dari {url} bukan JSON")
    if isinstance(isi, dict) and isi.get("error"):
        raise RuntimeError(f"Open-Meteo menolak permintaan: {isi.get('reason')}")
    r.raise_for_status()
    return isi


def tabel_dari_api(kode_sel):
    """Susun tabel pengamatan dari Open-Meteo, cara yang sama dengan notebook.

    Return: (tabel, koordinat) — koordinat berisi kisi yang dikembalikan kedua
    API, untuk dicocokkan dengan kolom lintang_kisi/bujur_kisi tabel LOKASI.
    """
    lat, lon, elev = SEL_GRID[kode_sel]
    koordinat = {}

    isi = _minta(API_SO2, {"latitude": lat, "longitude": lon, "elevation": elev,
                           "hourly": "sulphur_dioxide", "domains": DOMAIN_SO2,
                           "past_days": HARI_MUNDUR, "forecast_days": 1,
                           "timezone": ZONA})
    koordinat["so2"] = (isi.get("latitude"), isi.get("longitude"), isi.get("elevation"))
    so2 = pd.DataFrame({
        "time": pd.to_datetime(isi["hourly"]["time"]),
        "so2": pd.to_numeric(isi["hourly"]["sulphur_dioxide"], errors="coerce"),
    }).dropna(subset=["so2"])
    so2["so2"] = so2["so2"].clip(lower=0)

    # Jendela arsip dalam hari UTC; alasannya ada di penarikan.tarik_sel().
    akhir_utc = pd.Timestamp.now(tz="UTC").normalize().tz_localize(None)
    isi = _minta(API_METEO, {
        "latitude": lat, "longitude": lon, "elevation": elev,
        "start_date": (akhir_utc - timedelta(days=HARI_MUNDUR)).strftime("%Y-%m-%d"),
        "end_date": akhir_utc.strftime("%Y-%m-%d"),
        "hourly": ",".join(VAR_METEO), "models": MODEL_METEO,
        "timezone": "UTC", **SATUAN})
    koordinat["meteo"] = (isi.get("latitude"), isi.get("longitude"), isi.get("elevation"))
    meteo = pd.DataFrame({"time": pd.to_datetime(isi["hourly"]["time"], utc=True)})
    for v in VAR_METEO:
        meteo[v] = pd.to_numeric(isi["hourly"][v], errors="coerce")
    meteo["time"] = meteo["time"].dt.tz_convert(ZONA).dt.tz_localize(None)
    meteo = meteo.dropna(subset=VAR_METEO)

    gabung = so2.merge(meteo, on="time", how="inner", validate="one_to_one")
    return gabung.sort_values("time").set_index("time"), koordinat


def cetak_koordinat(kode_sel, koordinat, sambungan):
    """Bandingkan kisi yang dikembalikan API dengan kolom kisi tabel LOKASI."""
    with sambungan.cursor() as k:
        k.execute("SELECT lintang_kisi, bujur_kisi FROM lokasi WHERE kode_sel=%s",
                  (kode_sel,))
        b = k.fetchone()
    print("Koordinat kisi yang dikembalikan API")
    print(f"  SO2   : {koordinat['so2'][0]}, {koordinat['so2'][1]}  "
          f"(elevasi {koordinat['so2'][2]})")
    print(f"  cuaca : {koordinat['meteo'][0]}, {koordinat['meteo'][1]}  "
          f"(elevasi {koordinat['meteo'][2]})")
    if b and b["lintang_kisi"] is not None:
        cocok = (abs(float(b["lintang_kisi"]) - koordinat["so2"][0]) < 1e-4 and
                 abs(float(b["bujur_kisi"]) - koordinat["so2"][1]) < 1e-4)
        print(f"  LOKASI: {b['lintang_kisi']}, {b['bujur_kisi']}  "
              f"-> {'COCOK' if cocok else 'TIDAK COCOK, sel berbeda!'}")
    print()


def _beda(nama, a, b):
    """Selisih dua nilai, dengan perlakuan khusus untuk besaran sirkular.

    Arah angin sirkular: 0 dan 360 derajat sama. Basis data menormalkan 360
    menjadi 0 (kekangan ck_pengamatan_arah_angin), sedangkan Open-Meteo tetap
    360; selisih lurus 360 menyesatkan padahal sin/cos-nya sama.
    """
    d = abs(float(a) - float(b))
    if nama == "wind_direction_10m":
        d = min(d, 360.0 - d)
    return d


def diagnosa(kode_sel, sambungan):
    """Bandingkan basis data dan API pada SELURUH jam yang beririsan.

    Memperlihatkan batas antara jam analisis (cocok) dan jam yang masih
    prakiraan saat seed ditarik (berbeda).
    """
    tabel_api, koordinat = tabel_dari_api(kode_sel)
    cetak_koordinat(kode_sel, koordinat, sambungan)

    tabel_db, _ = bd.ambil_pengamatan_terakhir(sambungan, kode_sel, None, 120)
    irisan = sorted(set(tabel_db.index) & set(tabel_api.index))
    if not irisan:
        print("Tidak ada jam yang beririsan antara basis data dan API.")
        return 1

    kolom = ["so2"] + VAR_METEO
    print(f"{len(irisan)} jam beririsan, {irisan[0]} sampai {irisan[-1]}\n")
    print(f"{'jam':<18}{'cocok':>7}  {'SO2 db/api':>16}  {'suhu db/api':>14}  keterangan")
    n_cocok = 0
    batas = None
    for t in irisan:
        beda = [k for k in kolom
                if _beda(k, tabel_db.loc[t, k], tabel_api.loc[t, k]) > 1e-9]
        if not beda:
            n_cocok += 1
        elif batas is None:
            batas = t
        print(f"{str(t):<18}{'YA' if not beda else f'{len(beda)}/9':>7}  "
              f"{tabel_db.loc[t,'so2']:>7.1f}/{tabel_api.loc[t,'so2']:<8.1f}  "
              f"{tabel_db.loc[t,'temperature_2m']:>6.1f}/{tabel_api.loc[t,'temperature_2m']:<7.1f}  "
              f"{'' if not beda else ', '.join(b[:14] for b in beda[:3])}")

    print(f"\n  jam identik : {n_cocok} dari {len(irisan)}")
    if batas is not None:
        print(f"  mulai berbeda pada : {batas}")
    print("\nTafsiran: selisih pada jam-jam terakhir wajar (prakiraan yang sudah")
    print("diperbarui); selisih pada jam lama berarti ada masalah. Batas biasanya")
    print("jatuh pada 07.00 atau 19.00 WIB (run model 00z dan 12z).")
    return 0


def banding_target(kode_sel, target, toleransi, sambungan):
    """Bandingkan vektor fitur dan prediksi untuk satu jam target."""
    bundel = md.muat_model(kode_sel)
    fitur = bundel["fitur"]

    batas = (target - pd.Timedelta(hours=1)).to_pydatetime()
    tabel_db, _ = bd.ambil_pengamatan_terakhir(sambungan, kode_sel, batas)
    tabel_db = md.sandikan_arah_angin(tabel_db)
    tabel_api, koordinat = tabel_dari_api(kode_sel)
    cetak_koordinat(kode_sel, koordinat, sambungan)
    tabel_api = md.sandikan_arah_angin(tabel_api)

    jam_lag = [target - pd.Timedelta(hours=lag) for lag in LAGS]
    kurang = [j for j in jam_lag if j not in tabel_api.index]
    if kurang:
        print("Open-Meteo tidak memuat jam " + ", ".join(str(j) for j in kurang))
        return 1

    X_db = md.susun_vektor_fitur(tabel_db, target, fitur)
    X_api = md.susun_vektor_fitur(tabel_api, target, fitur)
    beda = np.abs(X_db - X_api)[0]

    print(f"Sel {kode_sel}, jam target {target}")
    print(f"\nPerbandingan {len(fitur)} fitur:")
    n_beda = 0
    for nama, v_db, v_api, d in zip(fitur, X_db[0], X_api[0], beda):
        if d > toleransi:
            n_beda += 1
            print(f"  BERBEDA {nama:<28} basis data {v_db:>10.4f}  API {v_api:>10.4f}"
                  f"  selisih {d:.6f}")
    print(f"  fitur identik : {len(fitur)-n_beda} dari {len(fitur)}")

    h_db = md.prediksi_stacking(bundel, X_db)
    h_api = md.prediksi_stacking(bundel, X_api)
    print("\nHasil prediksi:")
    for k in ("xgboost", "random_forest", "stacking"):
        print(f"  {k:<15} basis data {h_db[k]:>10.6f}   API {h_api[k]:>10.6f}"
              f"   selisih {abs(h_db[k]-h_api[k]):.3e}")

    if n_beda:
        print(f"\nTIDAK IDENTIK — {n_beda} fitur berbeda.")
        print("Jalankan --diagnosa untuk melihat apakah selisih hanya pada jam")
        print("terakhir seed (wajar) atau juga pada jam lama (seed bermasalah).")
    else:
        print("\nLOLOS — kedua jalur identik.")
    return 0 if n_beda == 0 else 1


def main():
    """Titik masuk CLI: membandingkan data basis data dengan Open-Meteo per jam dan melaporkan selisihnya."""
    p = argparse.ArgumentParser(description="Bandingkan jalur basis data dan API")
    p.add_argument("--sel", required=True)
    p.add_argument("--target", help="jam yang diprediksi, 'YYYY-MM-DD HH:MM'")
    p.add_argument("--diagnosa", action="store_true",
                   help="bandingkan seluruh jam yang beririsan, per jam")
    p.add_argument("--toleransi", type=float, default=1e-9)
    a = p.parse_args()

    md.periksa_versi_sesi()
    with bd.koneksi() as sambungan:
        if a.diagnosa:
            return diagnosa(a.sel, sambungan)
        if a.target:
            target = pd.Timestamp(a.target)
        else:
            t, _ = bd.ambil_pengamatan_terakhir(sambungan, a.sel, None, 1)
            target = t.index[-1] + pd.Timedelta(hours=1)
        return banding_target(a.sel, target, a.toleransi, sambungan)


if __name__ == "__main__":
    sys.exit(main())
