"""Tambahkan kolom rincian langkah pada SIKLUS_SINKRONISASI, lalu perbaiki
status siklus lampau yang tercatat salah.

    python migrasi_kolom_langkah.py --periksa       # lihat saja, tidak menulis
    python migrasi_kolom_langkah.py --hanya-kolom   # tambah kolom, riwayat utuh
    python migrasi_kolom_langkah.py --terapkan      # kolom + betulkan riwayat

MENGAPA BERKAS TERSENDIRI, BUKAN DI PENJADWAL

Peran aplikasi so2_app sengaja tidak diberi hak DDL; pemilik tabel adalah
postgres. Penjadwal karena itu tidak dapat -- dan tidak seharusnya -- menambah
kolom sendiri. Jalankan berkas ini sekali sebagai pemilik, dengan PG_USER dan
PG_PASSWORD milik postgres di lingkungan, misalnya:

    PG_USER=postgres PG_PASSWORD=... python migrasi_kolom_langkah.py --terapkan

Tanpa migrasi ini sistem tetap berjalan: status gabungan sudah tersimpan, dan
kolom rincian hanya tampil kosong di riwayat.

PEMBETULAN STATUS LAMPAU

Sampai 1 Oktober 2026 status siklus disegel oleh langkah penarikan, sebelum
langkah prediksi berjalan. Siklus yang kehilangan SELURUH prediksinya karena itu
tercatat 'berhasil'. Baris seperti itu dikenali dari ketiadaan prediksi pada jam
yang menjadi target siklus tersebut, dan statusnya dibetulkan menjadi 'gagal'.
Hanya status yang disentuh; pengamatan tidak diubah sama sekali.
"""
import argparse
import sys

import basis_data as bd

# Siklus penjadwal yang berstatus 'berhasil' dengan kesepuluh sel tertarik,
# tetapi tidak satu pun baris PREDIKSI terbentuk dalam rentang siklus itu.
# Rentangnya dibatasi waktu_mulai siklus berikutnya supaya tiap prediksi hanya
# dihitung untuk satu siklus.
SQL_SALAH_CATAT = """
WITH batas AS (
    SELECT id_siklus, waktu_mulai, status, jumlah_berhasil, jumlah_gagal,
           lead(waktu_mulai) OVER (ORDER BY waktu_mulai) AS waktu_mulai_berikut
    FROM   siklus_sinkronisasi
)
SELECT b.id_siklus, b.waktu_mulai, b.status
FROM   batas b
WHERE  b.status = 'berhasil'
  AND  b.jumlah_gagal = 0
  AND  NOT EXISTS (
         SELECT 1 FROM prediksi p
         WHERE  p.dibuat_pada >= b.waktu_mulai
           AND (b.waktu_mulai_berikut IS NULL
                OR p.dibuat_pada < b.waktu_mulai_berikut))
ORDER  BY b.waktu_mulai
"""

SQL_BETULKAN = """
UPDATE siklus_sinkronisasi
SET    status = 'gagal', prediksi_berhasil = 0,
       prediksi_gagal = jumlah_berhasil
WHERE  id_siklus = ANY(%(id)s)
"""


def main():
    p = argparse.ArgumentParser(description="Migrasi kolom rincian langkah")
    kel = p.add_mutually_exclusive_group(required=True)
    kel.add_argument("--periksa", action="store_true",
                     help="tampilkan rencana tanpa menulis apa pun")
    kel.add_argument("--hanya-kolom", action="store_true", dest="hanya_kolom",
                     help="tambahkan kolom saja, jangan sentuh riwayat lampau")
    kel.add_argument("--terapkan", action="store_true",
                     help="tambahkan kolom DAN betulkan status siklus lampau")
    p.add_argument("--siklus", help="batasi pembetulan pada id_siklus tertentu, "
                                    "dipisah koma, misalnya 28,29,30")
    a = p.parse_args()

    pilih = None
    if a.siklus:
        pilih = {int(x) for x in a.siklus.split(",") if x.strip()}

    # --hanya-kolom cukup untuk menambah kolom; penulisan kolom tetap perlu
    # hak pemilik tabel, sama seperti --terapkan.
    tulis_kolom = a.terapkan or a.hanya_kolom

    with bd.koneksi() as sambungan:
        sudah = bd.ada_kolom_langkah(sambungan)
        print(f"Kolom rincian langkah: {'sudah ada' if sudah else 'belum ada'}")

        if not sudah:
            if not tulis_kolom:
                print("  --hanya-kolom atau --terapkan akan menambahkan "
                      "prediksi_berhasil, prediksi_gagal, aktual_terisi.")
            else:
                try:
                    bd.siapkan_kolom_langkah(sambungan)
                    sambungan.commit()
                    print("  Kolom ditambahkan.")
                    sudah = True
                except Exception as e:                  # noqa: BLE001
                    sambungan.rollback()
                    print(f"  GAGAL menambah kolom: {type(e).__name__}: {e}")
                    print("  Jalankan ulang sebagai pemilik tabel (postgres).")
                    return 1

        with sambungan.cursor() as k:
            k.execute(SQL_SALAH_CATAT)
            salah = k.fetchall()
        if pilih is not None:
            salah = [b for b in salah if b["id_siklus"] in pilih]

        if a.hanya_kolom:
            print(f"\n{len(salah)} siklus lampau masih tercatat salah, "
                  "TIDAK disentuh (--hanya-kolom).")
            print("  Jalankan --terapkan bila kelak ingin membetulkannya.")
            return 0

        if not salah:
            print("Tidak ada siklus lampau yang salah tercatat.")
            return 0

        print(f"\n{len(salah)} siklus tercatat 'berhasil' padahal tidak satu pun "
              "prediksi terbentuk:")
        for b in salah:
            print(f"  id_siklus {b['id_siklus']:>4}  mulai {b['waktu_mulai']}")

        if not a.terapkan:
            print("\nMode periksa: tidak ada yang ditulis. "
                  "Tambahkan --terapkan untuk membetulkan statusnya.")
            return 0

        if not sudah:
            print("\nKolom rincian belum ada; status tetap dibetulkan tanpa "
                  "mengisi rinciannya.")
            with sambungan.cursor() as k:
                k.execute("""UPDATE siklus_sinkronisasi SET status = 'gagal'
                             WHERE id_siklus = ANY(%(id)s)""",
                          {"id": [b["id_siklus"] for b in salah]})
        else:
            with sambungan.cursor() as k:
                k.execute(SQL_BETULKAN, {"id": [b["id_siklus"] for b in salah]})
        sambungan.commit()
        print(f"\n{len(salah)} baris dibetulkan menjadi 'gagal'.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
