"""berkas model Colab -> berkas model portabel.

Kesepuluh berkas `Gxx_skenario2_model.joblib` dilatih di Google Colab (Linux).
Di Windows, `joblib.load` atasnya gagal dengan `XGBoostError: input stream
corrupted`. Berkasnya TIDAK rusak — berkas yang sama berhasil dimuat di Linux
dengan versi pustaka yang persis sama, dan SHA-256-nya cocok.

Penyebabnya adalah buffer pickle XGBoost dibuat oleh `XGBoosterSerializeToBuffer`,
dan format itu memang tidak dijamin portabel antarsistem operasi. Dokumentasi
XGBoost menganjurkan `save_model` dengan format JSON atau UBJSON untuk
penyimpanan yang harus dipindah-pindah. RandomForest dan Ridge tidak terkena
masalah ini karena keduanya pickle scikit-learn biasa yang portabel.

Booster XGBoost sudah dikonversi lebih dahulu menjadi `Gxx_xgb.ubj` di folder
`model_portabel`. Berkas ini melengkapinya: membuka tiap berkas asli dengan
pemulihan booster dinonaktifkan sementara, lalu menyimpan RandomForest, Ridge,
dan metadatanya ke `Gxx_bundel.joblib` di folder yang sama.

Jalankan SEKALI:

    python konversi_model.py

Sesudah itu `model.py` hanya memakai berkas di `model_portabel`, dan tidak ada
lagi penonaktifan apa pun di kode yang berjalan setiap hari.
"""
import json
import sys
from contextlib import contextmanager
from pathlib import Path

import joblib
import xgboost as xgb
import xgboost.core

from konfigurasi import FOLDER_MODEL, FOLDER_MODEL_ASLI, KODE_SEL


@contextmanager
def booster_tidak_dipulihkan():
    """Nonaktifkan sementara pemulihan booster XGBoost saat unpickle.

    Hanya dipakai di berkas konversi ini, tidak pernah di kode yang berjalan.
    Booster yang dihasilkan sengaja dibiarkan kosong (handle None) lalu dibuang;
    yang diambil dari berkas asli hanya RandomForest, Ridge, dan metadata.
    """
    asli = xgboost.core.Booster.__setstate__

    def lewati(self, state):
        """Pengganti __setstate__ XGBoost: memulihkan atribut tanpa memuat buffer Booster yang tak terbaca di Windows."""
        state = dict(state)
        state["handle"] = None          # jangan panggil UnserializeFromBuffer
        self.__dict__.update(state)

    xgboost.core.Booster.__setstate__ = lewati
    try:
        yield
    finally:
        xgboost.core.Booster.__setstate__ = asli


def main():
    """Titik masuk CLI: mengonversi kesepuluh berkas model Colab menjadi berkas portabel."""
    if not FOLDER_MODEL_ASLI.exists():
        print(f"FOLDER_MODEL_ASLI tidak ditemukan: {FOLDER_MODEL_ASLI}")
        return 1
    FOLDER_MODEL.mkdir(parents=True, exist_ok=True)

    berkas_meta = FOLDER_MODEL / "metadata_model.json"
    meta = json.loads(berkas_meta.read_text(encoding="utf-8")) if berkas_meta.exists() else {}

    galat = 0
    for kode in KODE_SEL:
        asal = FOLDER_MODEL_ASLI / f"{kode}_skenario2_model.joblib"
        ubj = FOLDER_MODEL / f"{kode}_xgb.ubj"
        tujuan = FOLDER_MODEL / f"{kode}_bundel.joblib"

        if not asal.exists():
            print(f"{kode}: berkas asli tidak ada -> {asal}"); galat += 1; continue
        if not ubj.exists():
            print(f"{kode}: {ubj.name} tidak ada, tidak bisa dilanjutkan"); galat += 1; continue

        try:
            with booster_tidak_dipulihkan():
                b = joblib.load(asal)

            if b["kode_sel"] != kode or b["skenario"] != 2:
                print(f"{kode}: isi berkas tidak cocok dengan namanya"); galat += 1; continue

            joblib.dump({
                "kode_sel": b["kode_sel"],
                "skenario": b["skenario"],
                "fitur": b["fitur"],
                "variabel_terpilih": b["variabel_terpilih"],
                "lingkungan": b["lingkungan"],
                "rf": b["rf"],
                "ridge": b["ridge"],
            }, tujuan, compress=3)

            # Pemeriksaan: fitur pada bundel harus cocok dengan metadata hasil
            # konversi booster, supaya .ubj dan .joblib tidak pernah tertukar.
            if kode in meta and meta[kode]["fitur"] != b["fitur"]:
                print(f"{kode}: PERINGATAN daftar fitur berbeda dari metadata")
                galat += 1

            muat = xgb.XGBRegressor(); muat.load_model(ubj)
            ukuran = tujuan.stat().st_size / 1e6
            print(f"{kode}: {len(b['fitur'])} fitur, bundel {ukuran:.1f} MB, "
                  f"booster {muat.n_features_in_} fitur  OK")
        except Exception as e:                          # noqa: BLE001
            print(f"{kode}: GAGAL {type(e).__name__}: {e}"); galat += 1

    print("\n" + ("Konversi selesai. Jalankan uji_koneksi.py lalu jalankan_prediksi.py."
                  if galat == 0 else f"{galat} sel bermasalah."))
    return 1 if galat else 0


if __name__ == "__main__":
    sys.exit(main())
