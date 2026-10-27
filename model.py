"""Pemuatan model dan inferensi stacking.

Fungsi di berkas ini disalin dari ModulInferensiFIX.ipynb supaya
angkanya identik. Yang berubah hanya asal datanya, tabel pengamatan sekarang
datang dari PostgreSQL, bukan dari Open-Meteo.
"""
from functools import lru_cache

import joblib
import numpy as np
import pandas as pd
import sklearn
import xgboost as xgb

from konfigurasi import (AMBANG_KATEGORI, BAKU_MUTU_1_JAM, BATAS_KEMUTAKHIRAN_JAM,
                         FOLDER_MODEL, KATEGORI_TERATAS, LAGS, SKENARIO, ZONA)

VERSI_TERKUNCI = {"scikit-learn": "1.6.1", "xgboost": "3.4.1"}


def versi_terpasang():
    """Versi pustaka yang BENAR-BENAR terpasang di sesi ini.

    Dipisah menjadi fungsi sendiri supaya muat_model() dapat membandingkan
    berkas model terhadap versi yang nyata, bukan terhadap konstanta.
    """
    return {"scikit-learn": sklearn.__version__, "xgboost": xgb.__version__}


def periksa_versi_sesi():
    """Hentikan program kalau versi pustaka sesi ini berbeda dari saat pelatihan."""
    aktif = versi_terpasang()
    for nama, versi in VERSI_TERKUNCI.items():
        if aktif[nama] != versi:
            raise RuntimeError(
                f"{nama} yang aktif {aktif[nama]}, seharusnya {versi}. "
                "Pasang ulang dengan: pip install -r requirements.txt")


@lru_cache(maxsize=10)
def muat_model(kode):
    """Muat satu model sel grid dari berkas portabel, simpan di memori.

    Model tersimpan dalam dua berkas:
      Gxx_xgb.ubj      booster XGBoost, format UBJSON resmi XGBoost
      Gxx_bundel.joblib RandomForest, Ridge, daftar fitur, dan metadata

    Berkas `.joblib` asli dari Colab TIDAK dipakai di sini. Buffer pickle
    XGBoost di dalamnya tidak portabel dari Linux ke Windows dan menimbulkan
    `XGBoostError: input stream corrupted`. Lihat konversi_model.py.

    lru_cache membuat berkas hanya dibaca sekali per proses. Tanpa ini,
    sepuluh berkas RandomForest sebesar rata-rata 39 MB akan dibaca ulang
    setiap siklus penjadwal.
    """
    berkas_bundel = FOLDER_MODEL / f"{kode}_bundel.joblib"
    berkas_ubj = FOLDER_MODEL / f"{kode}_xgb.ubj"
    for b in (berkas_bundel, berkas_ubj):
        if not b.exists():
            raise FileNotFoundError(
                f"Berkas model tidak ditemukan: {b}\n"
                "Jalankan konversi_model.py sekali lebih dahulu.")

    bundel = joblib.load(berkas_bundel)

    # Versi pustaka saat pelatihan diperiksa per berkas, bukan hanya versi sesi.
    #
    # Pembandingnya adalah versi yang BENAR-BENAR terpasang, bukan konstanta
    # VERSI_TERKUNCI. Sebelum 30 September 2026 perbandingannya konstanta lawan
    # konstanta, sehingga pemeriksaan ini tidak pernah dapat mendeteksi sesi
    # yang memasang versi berbeda — dan pesan galatnya menyebut "sesi ini
    # memakai {versi}" padahal yang dicetak adalah konstanta, bukan versi sesi.
    aktif = versi_terpasang()
    for nama in VERSI_TERKUNCI:
        if bundel["lingkungan"][nama] != aktif[nama]:
            raise RuntimeError(
                f"{kode} dilatih dengan {nama} {bundel['lingkungan'][nama]}, "
                f"sesi ini memasang {aktif[nama]}. Angka prediksi tidak dapat "
                "dijamin sama. Pasang ulang dengan: pip install -r requirements.txt")

    if bundel["skenario"] != SKENARIO or bundel["kode_sel"] != kode:
        raise RuntimeError(f"{kode}: isi berkas model tidak cocok dengan namanya")

    model_xgb = xgb.XGBRegressor()
    model_xgb.load_model(berkas_ubj)
    if model_xgb.n_features_in_ != len(bundel["fitur"]):
        raise RuntimeError(
            f"{kode}: booster menerima {model_xgb.n_features_in_} fitur, "
            f"bundel menyebut {len(bundel['fitur'])}. Berkas tertukar.")
    bundel["xgb"] = model_xgb

    return bundel


def sandikan_arah_angin(tabel):
    """Tambah kolom wind_dir_sin dan wind_dir_cos (Persamaan 2.17 naskah).

    Arah angin bersifat siklis: 1 derajat dan 359 derajat hampir sama arahnya
    tetapi selisih angkanya 358. Sinus dan kosinus memetakannya ke lingkaran
    satuan. Keduanya fitur turunan, karena itu tidak disimpan di basis data.
    """
    tabel = tabel.copy()
    radian = np.deg2rad(tabel["wind_direction_10m"])
    tabel["wind_dir_sin"] = np.sin(radian)
    tabel["wind_dir_cos"] = np.cos(radian)
    return tabel


def jam_sekarang():
    """Jam berjalan waktu Jakarta, dibulatkan ke bawah, tanpa zona waktu."""
    return pd.Timestamp.now(tz=ZONA).tz_localize(None).floor("h")


def tentukan_waktu_target(tabel, sekarang=None,
                          batas_kemutakhiran=BATAS_KEMUTAKHIRAN_JAM):
    """Tentukan jam yang diprediksi, dan tolak kalau datanya sudah basi.

    Jam terbaru yang lengkap berperan sebagai t-1, jadi yang diprediksi satu jam
    sesudahnya. Karena jam target dihitung dari baris terakhir yang ada dan bukan
    dari jam berjalan, data yang tertinggal akan menggeser jam target ke masa
    lalu tanpa memunculkan galat apa pun. Itu sebabnya ketertinggalan diperiksa.
    """
    if tabel.empty:
        raise RuntimeError("Tidak ada satu pun pengamatan untuk sel ini")

    waktu_terakhir = tabel.index[-1]
    if sekarang is None:
        sekarang = jam_sekarang()
    tertinggal = int((sekarang - waktu_terakhir) / pd.Timedelta(hours=1))

    if tertinggal > batas_kemutakhiran:
        raise RuntimeError(
            f"Pengamatan terbaru pukul {waktu_terakhir} tertinggal {tertinggal} jam "
            f"dari jam berjalan {sekarang}, melewati ambang {batas_kemutakhiran} jam. "
            "Prediksi tidak dibentuk.")

    return waktu_terakhir + pd.Timedelta(hours=1)


def susun_vektor_fitur(tabel, waktu_target, fitur):
    """Susun satu baris fitur untuk diprediksi.

    Return: matriks 1 x n, urutan kolomnya mengikuti daftar fitur berkas model.

    Ketiga jam harus ada dan berurutan. Kalau satu saja hilang, fungsi berhenti,
    karena mengisi lubang dengan nilai terdekat berarti memberi model masukan
    yang tidak pernah dilihatnya saat dilatih.
    """
    nilai = {}
    for lag in LAGS:
        jam = waktu_target - pd.Timedelta(hours=lag)
        if jam not in tabel.index:
            raise RuntimeError(
                f"Pengamatan pukul {jam} tidak tersedia, lag t-{lag} tidak terbentuk.")
        baris = tabel.loc[jam]
        for kolom in tabel.columns:
            nilai[f"{kolom}_t{lag}"] = float(baris[kolom])

    kurang = [f for f in fitur if f not in nilai]
    if kurang:
        raise RuntimeError("Fitur tidak terbentuk dari data: " + ", ".join(kurang))

    # Urutan disalin dari daftar fitur milik model, tidak disusun di sini. Model
    # pohon menerima matriks angka tanpa nama kolom, jadi kolom yang tertukar
    # tidak akan memunculkan galat apa pun, hanya angka yang salah diam-diam.
    return np.array([[nilai[f] for f in fitur]], dtype=float)


def prediksi_stacking(bundel, X):
    """Jalankan stacking pada satu baris fitur.

    Urutan kolom z = [XGB, RF] tidak boleh dibalik. Bobot Ridge dipelajari untuk
    urutan itu; membaliknya berarti menukar bobot kedua model dasar.
    """
    p_xgb = float(bundel["xgb"].predict(X)[0])
    p_rf = float(bundel["rf"].predict(X)[0])
    z = np.column_stack([[p_xgb], [p_rf]])
    p_stack_mentah = float(bundel["ridge"].predict(z)[0])

    # Dipangkas pada nol dengan alasan yang sama seperti pemangkasan pra-pemrosesan
    # Subbab 2.1.5. Prediksi model dasar sengaja TIDAK dipangkas, karena keduanya
    # masukan bagi Ridge dan bobot Ridge dipelajari atas nilai yang tidak dipangkas.
    return {"xgboost": p_xgb, "random_forest": p_rf,
            "stacking": max(0.0, p_stack_mentah), "stacking_mentah": p_stack_mentah}


def kategori_kualitas_udara(nilai):
    """Terjemahkan konsentrasi menjadi kategori Tabel 2.1 dan rasio baku mutu."""
    label = KATEGORI_TERATAS
    for batas, nama in AMBANG_KATEGORI:
        if nilai <= batas:
            label = nama
            break
    return {"kategori": label, "rasio_baku_mutu": nilai / BAKU_MUTU_1_JAM}
