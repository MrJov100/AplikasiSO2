"""Isi kolom nilai_aktual pada tabel PREDIKSI, lalu laporkan ketelitian.

Sebuah prediksi dibentuk untuk jam yang belum terjadi, sehingga nilai
sebenarnya baru diketahui satu jam kemudian. Modul ini mencari prediksi yang
jam targetnya sudah ada pengamatannya lalu mengisinya. Kolom `selisih` terisi
sendiri karena ia generated column.

    python isi_nilai_aktual.py            # coba-coba, tidak menulis
    python isi_nilai_aktual.py --simpan
    python isi_nilai_aktual.py --ketelitian

PENGAMATAN YANG DIKECUALIKAN

Nilai aktual TETAP diisi walaupun pengamatan jam itu berstatus 'dikecualikan',
supaya Halaman Riwayat Prediksi tetap menampilkan angkanya. Yang menyaringnya
adalah kueri ketelitian: membandingkan prediksi dengan nilai yang sudah dinilai
salah oleh admin akan mengotori MAE dan RMSE operasional Bab 4.

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

    print(f"\nKetelitian operasional atas {k['n']} prediksi")
    print("(pengamatan berstatus 'dikecualikan' tidak diikutkan)\n")
    print(f"  {'model':<18}{'MAE':>10}{'RMSE':>10}")
    print(f"  {'Stacking':<18}{k['mae_stacking']:>10}{k['rmse_stacking']:>10}")
    print(f"  {'XGBoost':<18}{k['mae_xgboost']:>10}{k['rmse_xgboost']:>10}")
    print(f"  {'Random Forest':<18}{k['mae_rf']:>10}{k['rmse_rf']:>10}")
    print(f"  {'Persistensi':<18}{k['mae_persistensi']:>10}{k['rmse_persistensi']:>10}")

    # Skill score terhadap baseline persistensi, seperti pada Bab 3 naskah.
    #
    # Definisi Bab 3 memakai rasio MSE, bukan rasio RMSE, sehingga rasionya
    # dikuadratkan. Rumus ini harus sama persis dengan LayananRiwayat.ketelitian
    # pada api/layanan.py: sebelumnya keduanya berbeda dan menghasilkan dua
    # angka skill score untuk data yang sama (0.173 di sini, 0.316 di aplikasi).
    if k["rmse_persistensi"] and float(k["rmse_persistensi"]) > 0:
        skill = 1 - (float(k["rmse_stacking"]) / float(k["rmse_persistensi"])) ** 2
        print(f"\n  Skill score stacking terhadap persistensi: {skill:.4f}")
    if int(k["n"]) < 100:
        print("\n  Peringatan: jumlahnya masih terlalu sedikit untuk disimpulkan.")


def main():
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
                  f"{'aktual':>10}{'selisih':>10}  status")
            for b in terisi[:20]:
                print(f"  {b['id_prediksi']:>5}{str(b['waktu_prediksi']):>22}"
                      f"{b['nilai_so2']:>11}{b['nilai_aktual']:>10}"
                      f"{b['selisih']:>10}  {b['status_pengamatan']}")
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
