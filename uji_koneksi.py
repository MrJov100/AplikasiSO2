"""Pemeriksaan cepat sebelum menjalankan apa pun.

    python uji_koneksi.py

Memeriksa empat hal berurutan: versi pustaka, keberadaan sepuluh berkas model,
koneksi ke PostgreSQL, dan hak akses peran so2_app atas tabel yang dibutuhkan.
"""
import sys

import basis_data as bd
import model as md
from konfigurasi import FOLDER_MODEL, KODE_SEL, PG


def main():
    """Titik masuk CLI: memeriksa versi pustaka, berkas model, koneksi PostgreSQL, dan hak akses."""
    galat = 0

    print("1. Versi pustaka")
    try:
        md.periksa_versi_sesi()
        import sklearn, xgboost, numpy, pandas
        print(f"   scikit-learn {sklearn.__version__}, xgboost {xgboost.__version__}, "
              f"numpy {numpy.__version__}, pandas {pandas.__version__}  OK")
    except Exception as e:                              # noqa: BLE001
        print(f"   GAGAL: {e}"); galat += 1

    print(f"\n2. Berkas model portabel di {FOLDER_MODEL}")
    hilang = [f"{k}{akhiran}" for k in KODE_SEL
              for akhiran in ("_xgb.ubj", "_bundel.joblib")
              if not (FOLDER_MODEL / f"{k}{akhiran}").exists()]
    if hilang:
        print(f"   GAGAL: tidak ditemukan {', '.join(hilang[:6])}"
              f"{' dan lainnya' if len(hilang) > 6 else ''}")
        print("   Jalankan konversi_model.py sekali lebih dahulu.")
        galat += 1
    else:
        print("   dua puluh berkas lengkap (10 .ubj + 10 bundel)  OK")
        try:
            b = md.muat_model("G04")
            print(f"   G04 termuat: {len(b['fitur'])} fitur, "
                  f"{', '.join(b['variabel_terpilih'])}  OK")
        except Exception as e:                          # noqa: BLE001
            print(f"   GAGAL memuat G04: {e}"); galat += 1

    print(f"\n3. Koneksi PostgreSQL ({PG['user']}@{PG['host']}:{PG['port']}/{PG['dbname']})")
    try:
        with bd.koneksi() as s, s.cursor() as k:
            k.execute("SELECT current_user AS peran, current_database() AS basis, "
                      "current_setting('TimeZone') AS zona")
            b = k.fetchone()
            print(f"   peran {b['peran']}, basis {b['basis']}, zona {b['zona']}  OK")
            if b["zona"] != "Asia/Jakarta":
                print(f"   PERINGATAN: zona waktu {b['zona']}, seharusnya Asia/Jakarta")

            k.execute("SELECT count(*) AS n FROM pengamatan")
            n = k.fetchone()["n"]
            k.execute("SELECT max(waktu) AS t FROM pengamatan")
            t = k.fetchone()["t"]
            print(f"   pengamatan: {n} baris, terbaru {t}")
            if n != 363770:
                print(f"   PERINGATAN: diharapkan 363770 baris")

            k.execute("SELECT count(*) AS n FROM lokasi")
            print(f"   lokasi    : {k.fetchone()['n']} baris")
            k.execute("SELECT count(*) AS n FROM prediksi")
            print(f"   prediksi  : {k.fetchone()['n']} baris")
    except Exception as e:                              # noqa: BLE001
        print(f"   GAGAL: {e}"); galat += 1

    print(f"\n4. Uji baca tiga pengamatan terakhir G04")
    try:
        with bd.koneksi() as s:
            tabel, id_waktu = bd.ambil_pengamatan_terakhir(s, "G04")
        print(f"   {len(tabel)} baris, {list(tabel.index)}")
        print(f"   id_pengamatan {list(id_waktu.values())}")
        print(f"   kolom: {', '.join(tabel.columns)}  OK")
    except Exception as e:                              # noqa: BLE001
        print(f"   GAGAL: {e}"); galat += 1

    print("\n" + ("SEMUA PEMERIKSAAN LOLOS" if galat == 0
                  else f"{galat} pemeriksaan GAGAL"))
    return 1 if galat else 0


if __name__ == "__main__":
    sys.exit(main())
