"""Isi kolom nilai_aktual pada tabel PREDIKSI, lalu laporkan ketelitian.

Sebuah prediksi dibentuk untuk jam yang belum terjadi, sehingga nilai
sebenarnya baru diketahui satu jam kemudian. Modul ini mencari prediksi yang
jam targetnya sudah ada pengamatannya lalu mengisinya. Kolom `selisih` terisi
sendiri karena ia generated column.

    python isi_nilai_aktual.py            # coba-coba, tidak menulis
    python isi_nilai_aktual.py --simpan
    python isi_nilai_aktual.py --ketelitian

CATATAN UNTUK BAB 4

Ketelitian di sini adalah ketelitian OPERASIONAL — prediksi yang benar-benar
dibentuk sistem saat berjalan, atas data yang tersedia pada saat itu. Ia tidak
sama dengan ketelitian blok uji pada Skenario 2, dan biasanya lebih buruk,
karena lag t-1 saat berjalan sering masih berupa prakiraan yang belum menjadi
analisis. Jangan membuat prediksi massal ke belakang untuk mengisi tabel ini:
prediksi seperti itu memakai data yang sudah direvisi dan akan terlihat lebih
baik daripada yang sebenarnya dicapai sistem.
"""
import argparse
import sys

import basis_data as bd


def cetak_ketelitian(sambungan):
    """Laporkan MAE dan RMSE operasional ketiga model beserta baseline."""
    k = bd.ketelitian_operasional(sambungan)
    if not k or not k["n"]:
        print("Belum ada prediksi yang nilai aktualnya terisi.")
        return

    jam_berbeda = int(k["jam_berbeda"] or 0)
    print(f"\nKetelitian operasional atas {k['n']} prediksi pada {jam_berbeda} jam berbeda")
    print(f"rentang {k['jam_awal']} - {k['jam_akhir']}")
    if int(k["n_tanpa_pendahulu"] or 0):
        print(f"{k['n_tanpa_pendahulu']} baris dikeluarkan: belum ada prediksi jam sebelumnya "
              "sebagai pembanding persistensi")
    print()
    print(f"  {'model':<24}{'MAE':>10}{'RMSE':>10}")
    print(f"  {'Stacking':<24}{k['mae_stacking']:>10}{k['rmse_stacking']:>10}")
    print(f"  {'XGBoost':<24}{k['mae_xgboost']:>10}{k['rmse_xgboost']:>10}")
    print(f"  {'Random Forest':<24}{k['mae_rf']:>10}{k['rmse_rf']:>10}")
    print(f"  {'Persistensi':<24}{k['mae_persistensi']:>10}{k['rmse_persistensi']:>10}")
    print(f"  {'Persistensi (arsip)':<24}{k['mae_persistensi_arsip']:>10}"
          f"{k['rmse_persistensi_arsip']:>10}")

    # Skill score terhadap baseline persistensi, seperti pada Bab 3 naskah.
    #
    # Definisi Bab 3 memakai rasio MSE, bukan rasio RMSE, sehingga rasionya
    # dikuadratkan. Rumus ini harus sama persis dengan LayananRiwayat.ketelitian
    # pada api/layanan.py: sebelumnya keduanya berbeda dan menghasilkan dua
    # angka skill score untuk data yang sama (0.173 di sini, 0.316 di aplikasi).
    if k["rmse_persistensi"] and float(k["rmse_persistensi"]) > 0:
        skill = 1 - (float(k["rmse_stacking"]) / float(k["rmse_persistensi"])) ** 2
        print(f"\n  Skill score stacking terhadap persistensi: {skill:.4f}")
    if k["rmse_persistensi_arsip"] and float(k["rmse_persistensi_arsip"]) > 0:
        skill_a = 1 - (float(k["rmse_stacking"]) / float(k["rmse_persistensi_arsip"])) ** 2
        print(f"  Skill score bila baseline dibaca dari arsip terevisi: {skill_a:.4f}")
        print("  (angka kedua terlalu tinggi; baris persistensi arsip dinilai terhadap"
              " potret\n   nilai aktual yang berbeda generasi, sehingga baselinenya terhukum)")

    # Ambang kecukupan dihitung dari JAM BERBEDA, bukan dari jumlah baris.
    # Satu siklus menghasilkan sepuluh baris sekaligus, dan kesepuluh sel grid
    # pada jam yang sama berbagi keadaan cuaca serta sumber lag yang sama
    # sehingga galatnya berkorelasi kuat. Ambang lama "n < 100" karena itu
    # terlalu longgar: n = 100 hanya berarti sepuluh jam operasi.
    if jam_berbeda < 30:
        print(f"\n  Peringatan: baru {jam_berbeda} jam berbeda. Sasaran 30-50 jam berbeda"
              " dengan cakupan siang dan malam sebelum angkanya disimpulkan.")
    kosong = [j for j in range(24) if j not in set(k["jam_tercakup"] or [])]
    if kosong:
        print(f"  Jam yang belum pernah tersampel: {kosong}")


def main():
    """Titik masuk CLI: mengisi nilai_aktual pada prediksi yang jamnya sudah terjadi, lalu melaporkan ketelitian."""
    p = argparse.ArgumentParser(description="Isi nilai aktual pada tabel PREDIKSI")
    p.add_argument("--simpan", action="store_true", help="tulis ke basis data")
    p.add_argument("--ketelitian", action="store_true",
                   help="hanya laporkan ketelitian, tanpa mengisi apa pun")
    a = p.parse_args()

    with bd.koneksi() as sambungan:
        if a.ketelitian:
            cetak_ketelitian(sambungan)
            return 0

        menunggu = bd.prediksi_menunggu(sambungan)
        print(f"Prediksi yang nilai aktualnya belum terisi: {menunggu['n']}"
              + (f", paling lama {menunggu['paling_lama']}" if menunggu["n"] else ""))

        terisi = bd.isi_nilai_aktual(sambungan)
        if not terisi:
            print("Tidak ada yang bisa diisi: pengamatan untuk jam targetnya "
                  "belum ada.")
        else:
            print(f"\n{len(terisi)} prediksi terisi:\n")
            print(f"  {'id':>5}{'waktu prediksi':>22}{'prediksi':>11}"
                  f"{'aktual':>10}{'selisih':>10}")
            for b in terisi[:20]:
                print(f"  {b['id_prediksi']:>5}{str(b['waktu_prediksi']):>22}"
                      f"{b['nilai_so2']:>11}{b['nilai_aktual']:>10}"
                      f"{b['selisih']:>10}")
            if len(terisi) > 20:
                print(f"  ... dan {len(terisi)-20} lagi")

        if a.simpan:
            sambungan.commit()
            print("\nPerubahan disimpan (commit).")
            cetak_ketelitian(sambungan)
        else:
            sambungan.rollback()
            print("\nMode coba-coba: dibatalkan. Tambahkan --simpan untuk menulis.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
