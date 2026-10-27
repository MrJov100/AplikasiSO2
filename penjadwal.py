"""Penjadwal per jam: segarkan pengamatan, bentuk prediksi, isi nilai aktual.

    python penjadwal.py              # jalan terus, hentikan dengan Ctrl+C
    python penjadwal.py --sekali     # jalankan satu siklus lalu berhenti

URUTAN LANGKAH

1. Segarkan pengamatan (paling dahulu, karena langkah 2 dan 3 membacanya).
2. Bentuk prediksi untuk kesepuluh sel dari tiga pengamatan terakhir.
3. Isi nilai aktual (terakhir, karena langkah 1 baru memasukkan pengamatan
   untuk jam target prediksi siklus sebelumnya).

Tiap langkah di-commit terpisah. Jika langkah 2 gagal, pengamatan tetap
tersimpan dan siklus berikutnya mencoba lagi.

JADWAL

- Berangkat pada menit ke-MENIT_JADWAL (bawaan 10, bisa diubah di .env), bukan
  menit nol: arsip Open-Meteo perlu waktu memuat jam yang baru lewat.
- Jika satu jalan belum selesai saat jadwal berikutnya tiba, jalan baru tidak
  dimulai (max_instances=1) dan jadwal yang terlewat digabung (coalesce=True),
  supaya panggilan API tidak menumpuk.
"""
import argparse
import sys
import time
import traceback
from datetime import datetime

import basis_data as bd
import jalankan_prediksi as jp
import model as md
import segarkan_pengamatan as sp
from konfigurasi import KODE_SEL, MENIT_JADWAL, VERSI_MODEL, ZONA


def catat(*bagian):
    """Mencetak pesan log dengan awalan waktu."""
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]", *bagian, flush=True)


def satu_siklus(simpan=True):
    """Jalankan ketiga langkah satu kali. Return True bila seluruhnya lancar.

    Status di SIKLUS_SINKRONISASI mencakup ketiga langkah, bukan hanya
    penarikan; kalau tidak, siklus yang kehilangan seluruh prediksinya tetap
    tampil 'berhasil' (lihat bd.SQL_SELESAI_TARIKAN).
    """
    lancar = True
    with bd.koneksi() as sambungan:
        # --- Langkah 1 ------------------------------------------------------
        catat("Langkah 1/3 — menyegarkan pengamatan")
        # segel_status=False: status akhir disetel di bawah, sesudah langkah 3.
        hasil = sp.jalankan_siklus(sambungan, KODE_SEL, simpan, cetak=catat,
                                   segel_status=False)
        if hasil["gagal"]:
            lancar = False
        if simpan:
            sambungan.commit()

        # --- Langkah 2 ------------------------------------------------------
        catat("Langkah 2/3 — membentuk prediksi")
        berhasil = gagal = 0
        for kode in KODE_SEL:
            try:
                h = jp.prediksi_satu_sel(sambungan, kode)
                if simpan:
                    baris = bd.simpan_prediksi(
                        sambungan, kode, h["waktu_prediksi"], h["waktu_dasar"],
                        h["id_lag"], h["hasil"], versi_model=VERSI_MODEL)
                    catat(f"  {kode} {h['waktu_prediksi']} "
                          f"{h['hasil']['stacking']:.2f} ug/m3 {h['kategori']} "
                          f"(id_prediksi {baris['id_prediksi']})")
                else:
                    catat(f"  {kode} {h['waktu_prediksi']} "
                          f"{h['hasil']['stacking']:.2f} ug/m3 {h['kategori']}")
                berhasil += 1
            except Exception as e:                      # noqa: BLE001
                gagal += 1
                lancar = False
                catat(f"  {kode} GAGAL: {type(e).__name__}: {e}")
        catat(f"  prediksi: {berhasil} berhasil, {gagal} gagal")
        if simpan:
            sambungan.commit()

        # --- Langkah 3 ------------------------------------------------------
        catat("Langkah 3/3 — mengisi nilai aktual")
        terisi = bd.isi_nilai_aktual(sambungan)
        catat(f"  {len(terisi)} prediksi terisi nilai aktualnya")
        if simpan:
            sambungan.commit()

        # --- Segel status siklus --------------------------------------------
        #
        # Jumlah yang dicatat tetap jumlah sel pada langkah penarikan; hanya
        # status yang kini menuntut ketiga langkah lancar. Prediksi gagal
        # seluruhnya = 'gagal', gagal sebagian = 'sebagian'.
        if simpan:
            if gagal == 0 and not hasil["gagal"]:
                status = "berhasil"
            elif berhasil == 0 and hasil["berhasil"] == 0:
                status = "gagal"
            elif berhasil == 0:
                # Pengamatan masuk, tetapi tidak ada prediksi: tetap kegagalan.
                status = "gagal"
            else:
                status = "sebagian"
            bd.selesaikan_siklus(sambungan, hasil["id_siklus"],
                                 hasil["berhasil"], hasil["gagal"], status)
            bd.catat_langkah_siklus(sambungan, hasil["id_siklus"],
                                    berhasil, gagal, len(terisi))
            sambungan.commit()
            catat(f"Siklus {hasil['id_siklus']} dicatat berstatus {status} "
                  f"(penarikan {hasil['berhasil']}/{len(KODE_SEL)}, "
                  f"prediksi {berhasil}/{len(KODE_SEL)}, aktual {len(terisi)})")
        else:
            sambungan.rollback()

    return lancar


def jalan_terjadwal():
    """Pembungkus supaya galat apa pun tidak menghentikan penjadwal."""
    catat("=" * 62)
    try:
        lancar = satu_siklus(simpan=True)
        catat("Siklus selesai" + ("" if lancar else " DENGAN KEGAGALAN"))
    except Exception:                                   # noqa: BLE001
        catat("Siklus berhenti karena galat tak terduga:")
        traceback.print_exc()


def main():
    """Titik masuk CLI: menjalankan satu siklus (--sekali/--coba) atau penjadwal per jam yang berjalan terus."""
    p = argparse.ArgumentParser(description="Penjadwal per jam")
    p.add_argument("--sekali", action="store_true",
                   help="jalankan satu siklus lalu berhenti")
    p.add_argument("--coba", action="store_true",
                   help="satu siklus tanpa menulis apa pun")
    a = p.parse_args()

    # Penjaga versi pustaka, dijalankan sekali SEBELUM siklus mana pun.
    # Penjadwal berjalan tanpa pengawasan dan mengisi tabel PREDIKSI; joblib.load
    # tetap berhasil dengan versi pustaka berbeda, tetapi angkanya berbeda dan
    # tanpa galat, sehingga catatan operasional tercemar diam-diam.
    md.periksa_versi_sesi()
    catat("Versi pustaka cocok dengan lingkungan pelatihan.")

    if a.coba:
        return 0 if satu_siklus(simpan=False) else 1
    if a.sekali:
        jalan_terjadwal()
        return 0

    # BackgroundScheduler, bukan BlockingScheduler: di Windows, Event.wait()
    # milik BlockingScheduler tidak dibangunkan Ctrl+C (bisa menunggu hampir
    # 3600 detik), sehingga terminal ditutup paksa dan koneksi basis data
    # terputus di tengah siklus. Utas utama kini menunggu dengan time.sleep()
    # pendek yang bisa dibatalkan Ctrl+C, lalu shutdown(wait=True) membiarkan
    # siklus yang sedang berjalan selesai.
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger

    penjadwal = BackgroundScheduler(timezone=ZONA)
    penjadwal.add_job(
        jalan_terjadwal,
        CronTrigger(minute=MENIT_JADWAL, timezone=ZONA),
        id="siklus_per_jam",
        max_instances=1,        # jangan menumpuk kalau satu jalan kepanjangan
        coalesce=True,          # jadwal yang terlewat digabung jadi satu
        misfire_grace_time=600)

    penjadwal.start()
    pekerjaan = penjadwal.get_job("siklus_per_jam")
    catat(f"Penjadwal menyala. Berangkat setiap jam pada menit ke-{MENIT_JADWAL} "
          f"waktu {ZONA}.")
    catat(f"Keberangkatan berikutnya: {pekerjaan.next_run_time}")
    catat("Hentikan dengan Ctrl+C.")

    try:
        while True:
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        catat("Ctrl+C diterima. Menunggu siklus yang sedang berjalan selesai…")
        penjadwal.shutdown(wait=True)
        catat("Penjadwal dihentikan.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
