"""Irisan tegak Fase 3a: basis data -> model -> basis data.

Membaca tiga pengamatan terakhir dari PostgreSQL, menjalankan stacking, lalu
menulis satu baris ke tabel PREDIKSI. Tidak ada panggilan ke Open-Meteo.

Contoh pemakaian:

    python jalankan_prediksi.py --sel G04
    python jalankan_prediksi.py --sel G04 --simpan
    python jalankan_prediksi.py --semua --simpan
    python jalankan_prediksi.py --sel G04 --batas "2026-09-27 23:00" --sekarang "2026-09-27 23:00"

Tanpa --simpan, program hanya menghitung dan menampilkan hasilnya. Jalankan
seperti itu dulu sebelum menulis apa pun ke basis data.
"""
import argparse
import sys

import pandas as pd

import basis_data as bd
import model as md
from konfigurasi import KODE_SEL, LAGS, VERSI_MODEL


def prediksi_satu_sel(sambungan, kode_sel, batas_waktu=None, sekarang=None):
    """Alur lengkap untuk satu sel grid. Return dict hasil."""
    tabel, id_per_waktu = bd.ambil_pengamatan_terakhir(sambungan, kode_sel, batas_waktu)
    tabel = md.sandikan_arah_angin(tabel)

    # Kalau batas_waktu diberi tanpa sekarang, jam itu dianggap jam berjalan,
    # supaya pemanggilan untuk jam lampau tidak tertolak penjaga kemutakhiran.
    if sekarang is None and batas_waktu is not None:
        sekarang = pd.Timestamp(batas_waktu)

    waktu_target = md.tentukan_waktu_target(tabel, sekarang=sekarang)

    bundel = md.muat_model(kode_sel)
    X = md.susun_vektor_fitur(tabel, waktu_target, bundel["fitur"])
    hasil = md.prediksi_stacking(bundel, X)
    kat = md.kategori_kualitas_udara(hasil["stacking"])

    jam_lag = [waktu_target - pd.Timedelta(hours=lag) for lag in LAGS]
    id_lag = [id_per_waktu[j] for j in jam_lag]

    return {
        "kode_sel": kode_sel,
        "waktu_prediksi": waktu_target,
        "waktu_dasar": jam_lag[0],
        "id_lag": id_lag,
        "jam_lag": jam_lag,
        "so2_lag": [float(tabel.loc[j, "so2"]) for j in jam_lag],
        "n_fitur": len(bundel["fitur"]),
        "variabel_terpilih": bundel["variabel_terpilih"],
        "hasil": hasil,
        **kat,
    }


def cetak(h):
    print(f"\n[{h['kode_sel']}] prediksi untuk {h['waktu_prediksi']}")
    print(f"  dasar t-1..t-3   : {', '.join(str(j) for j in h['jam_lag'])}")
    print(f"  id_pengamatan    : {h['id_lag']}")
    print(f"  SO2 t-1..t-3     : {h['so2_lag']}")
    print(f"  fitur            : {h['n_fitur']} ({', '.join(h['variabel_terpilih'])})")
    print(f"  XGBoost          : {h['hasil']['xgboost']:.4f}")
    print(f"  Random Forest    : {h['hasil']['random_forest']:.4f}")
    print(f"  Stacking (Ridge) : {h['hasil']['stacking']:.4f}"
          f"   [mentah {h['hasil']['stacking_mentah']:.4f}]")
    print(f"  kategori         : {h['kategori']}  "
          f"(rasio baku mutu {h['rasio_baku_mutu']:.2f})")


def main():
    p = argparse.ArgumentParser(description="Prediksi SO2 dari basis data")
    kel = p.add_mutually_exclusive_group(required=True)
    kel.add_argument("--sel", help="kode sel grid, misalnya G04")
    kel.add_argument("--semua", action="store_true", help="jalankan kesepuluh sel")
    p.add_argument("--batas", help="jangan pakai pengamatan setelah jam ini "
                                   "(format 'YYYY-MM-DD HH:MM')")
    p.add_argument("--sekarang", help="anggap jam berjalan adalah jam ini")
    p.add_argument("--simpan", action="store_true",
                   help="tulis hasilnya ke tabel PREDIKSI")
    a = p.parse_args()

    md.periksa_versi_sesi()

    batas = pd.Timestamp(a.batas).to_pydatetime() if a.batas else None
    sekarang = pd.Timestamp(a.sekarang) if a.sekarang else None
    daftar = KODE_SEL if a.semua else [a.sel]

    gagal = 0
    with bd.koneksi() as sambungan:
        for kode in daftar:
            try:
                h = prediksi_satu_sel(sambungan, kode, batas, sekarang)
                cetak(h)

                if a.simpan:
                    baris = bd.simpan_prediksi(
                        sambungan, kode, h["waktu_prediksi"], h["waktu_dasar"],
                        h["id_lag"], h["hasil"], versi_model=VERSI_MODEL)
                    print(f"  tersimpan        : id_prediksi={baris['id_prediksi']}")
                    print(f"  dari basis data  : {baris['kategori']}, "
                          f"rasio {baris['rasio_baku_mutu']}, "
                          f"melampaui={baris['melampaui_baku_mutu']}")

                    # Pemeriksaan silang: kolom terhitung basis data harus sama
                    # dengan hitungan Python. Kalau berbeda, salah satunya salah.
                    if baris["kategori"] != h["kategori"]:
                        print(f"  !! kategori BERBEDA: python {h['kategori']} "
                              f"vs basis data {baris['kategori']}")
                        gagal += 1
            except Exception as e:                      # noqa: BLE001
                print(f"\n[{kode}] GAGAL: {e}")
                gagal += 1

        if a.simpan:
            sambungan.commit()
            print("\nPerubahan disimpan (commit).")
        else:
            print("\nMode coba-coba: tidak ada yang ditulis. "
                  "Tambahkan --simpan untuk menulis ke basis data.")

    return 1 if gagal else 0


if __name__ == "__main__":
    sys.exit(main())
