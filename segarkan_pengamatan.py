"""Satu siklus sinkronisasi: tarik Open-Meteo, upsert ke PENGAMATAN.

Dipanggil penjadwal setiap jam, atau dijalankan tangan:

    python segarkan_pengamatan.py                  # coba-coba, tidak menulis
    python segarkan_pengamatan.py --simpan
    python segarkan_pengamatan.py --sel G04 --simpan
    python segarkan_pengamatan.py --simpan --pengguna admin

SELURUH JENDELA DI-UPSERT, BUKAN HANYA JAM TERBARU

Nilai jam-jam terakhir di arsip Open-Meteo masih berubah: yang ditarik sebelum
sebuah run selesai adalah prakiraan, lalu diganti analisis. Karena itu setiap
siklus menulis ulang seluruh jam yang ditarik (HARI_MUNDUR hari); kalau tidak,
prakiraan usang menetap dan dipakai sebagai lag.

DATA DISIMPAN APA ADANYA

Nilai disimpan seperti dari sumber, setelah pra-pemrosesan yang sama dengan
saat pelatihan (SO2 negatif dipangkas ke nol di penarikan.py). Tidak ada
penandaan atau perubahan nilai oleh sistem maupun admin. Nilai mustahil secara
fisika ditolak kekangan CHECK di basis data.
"""
import argparse
import sys
import time

import pandas as pd

import basis_data as bd
import penarikan as tarik
from konfigurasi import HARI_MUNDUR, KODE_SEL, SEL_GRID


def proses_sel(sambungan, kode_sel, id_siklus, simpan, batas_waktu=None):
    """Tarik dan simpan satu sel grid. Return dict ringkasan."""
    mulai = time.monotonic()
    lintang, bujur, elevasi = SEL_GRID[kode_sel]

    tabel, kisi = tarik.tarik_sel(lintang, bujur, elevasi, HARI_MUNDUR, batas_waktu)
    if tabel.empty:
        raise RuntimeError("tidak ada jam yang lengkap di kedua sumber")

    idl = bd.id_lokasi(sambungan, kode_sel)
    id_sinkronisasi = bd.buka_rincian(sambungan, id_siklus, kode_sel) if simpan else None

    masuk = diperbarui = 0
    for waktu, b in tabel.iterrows():
        baris = {k: (None if pd.isna(b[k]) else float(b[k]))
                 for k in tabel.columns}

        if simpan:
            disisipkan = bd.upsert_pengamatan(sambungan, {
                "id_lokasi": idl, "waktu": waktu.to_pydatetime(),
                "id_sinkronisasi": id_sinkronisasi,
                "so2": baris["so2"], "so2_mentah": baris["so2_mentah"],
                "suhu": baris["suhu"], "kelembapan": baris["kelembapan"],
                "titik_embun": baris["titik_embun"],
                "curah_hujan": baris["curah_hujan"],
                "tekanan_permukaan": baris["tekanan_permukaan"],
                "tutupan_awan": baris["tutupan_awan"],
                "kecepatan_angin": baris["kecepatan_angin"],
                "arah_angin": baris["arah_angin"]})
            masuk += disisipkan
            diperbarui += not disisipkan

    durasi = int((time.monotonic() - mulai) * 1000)
    if simpan:
        bd.tutup_rincian(sambungan, id_sinkronisasi, tabel.index[-1].to_pydatetime(),
                         masuk, diperbarui, "berhasil", None, durasi)

    return {"kode_sel": kode_sel, "baris": len(tabel), "masuk": masuk,
            "diperbarui": diperbarui, "waktu_terakhir": tabel.index[-1],
            "kisi": kisi, "durasi_ms": durasi}


def jalankan_siklus(sambungan, daftar=None, simpan=True, batas=None,
                    pemicu="penjadwal", id_pengguna=None, cetak=print,
                    segel_status=True):
    """Satu siklus penuh untuk beberapa sel. Dipakai CLI maupun penjadwal.

    Tidak melakukan commit; pemanggil yang memutuskan kapan menyimpan.

    segel_status=False membiarkan status siklus 'berjalan' agar pemanggil yang
    punya langkah lanjutan (penjadwal) menyetel status akhir sesudah semuanya
    selesai. Tanpa itu, kegagalan langkah berikutnya tidak terlihat di riwayat.
    """
    daftar = daftar or KODE_SEL
    id_siklus = bd.mulai_siklus(sambungan, pemicu, id_pengguna) if simpan else None
    if simpan:
        cetak(f"Siklus {id_siklus} dimulai (pemicu {pemicu})\n")

    cetak(f"{'sel':<5}{'baris':>7}{'sisip':>7}{'perbarui':>10}"
          f"{'ms':>7}  waktu terakhir")

    berhasil = gagal = 0
    for kode in daftar:
        mulai_sel = time.monotonic()
        try:
            # Tiap sel di savepoint-nya sendiri, bukan rollback(): rollback
            # membatalkan seluruh transaksi, termasuk baris siklus dari
            # mulai_siklus() yang belum di-commit, sehingga sinkronisasi gagal
            # tidak muncul di riwayat. Savepoint hanya membatalkan sel itu.
            if simpan:
                with sambungan.transaction():
                    r = proses_sel(sambungan, kode, id_siklus, simpan, batas)
            else:
                r = proses_sel(sambungan, kode, id_siklus, simpan, batas)
            berhasil += 1
            cetak(f"{kode:<5}{r['baris']:>7}{r['masuk']:>7}{r['diperbarui']:>10}"
                  f"{r['durasi_ms']:>7}  {r['waktu_terakhir']}")
        except Exception as e:                          # noqa: BLE001
            gagal += 1
            pesan = f"{type(e).__name__}: {e}"
            cetak(f"{kode:<5}  GAGAL: {pesan}")
            # Rincian dicatat sesudah savepoint dibatalkan, karena baris rincian
            # dari proses_sel() ikut hilang. Pencatatan ini juga di savepoint:
            # satu INSERT yang ditolak (mis. rincian sel sudah ada) akan
            # membatalkan seluruh transaksi dan semua perintah berikutnya gagal
            # dengan "InFailedSqlTransaction", padahal selesaikan_siklus() di
            # bawah masih harus menyegel status.
            if simpan:
                try:
                    with sambungan.transaction():
                        bd.catat_rincian_gagal(
                            sambungan, id_siklus, kode, pesan,
                            int((time.monotonic() - mulai_sel) * 1000))
                except Exception as e2:                 # noqa: BLE001
                    # Alasan kegagalan pencatatan ikut dicetak, bukan ditelan.
                    cetak(f"{'':<5}  (rincian galat {kode} tidak tercatat: "
                          f"{type(e2).__name__}: {e2})")

    status = None
    if simpan:
        if segel_status:
            status = bd.selesaikan_siklus(sambungan, id_siklus, berhasil, gagal)
            cetak(f"\nSiklus {id_siklus} selesai: {status} "
                  f"({berhasil} berhasil, {gagal} gagal)")
        else:
            status = bd.selesaikan_tarikan(sambungan, id_siklus, berhasil, gagal)
            cetak(f"\nPenarikan siklus {id_siklus}: {status} "
                  f"({berhasil} berhasil, {gagal} gagal)")
    return {"id_siklus": id_siklus, "status": status, "berhasil": berhasil,
            "gagal": gagal}


def main():
    """Titik masuk CLI: menjalankan satu siklus sinkronisasi pengamatan untuk satu atau semua sel."""
    p = argparse.ArgumentParser(description="Satu siklus sinkronisasi pengamatan")
    p.add_argument("--sel", help="satu sel saja, misalnya G04")
    p.add_argument("--simpan", action="store_true", help="tulis ke basis data")
    p.add_argument("--pengguna", help="username admin; menandai siklus sebagai manual")
    p.add_argument("--batas", help="anggap jam berjalan adalah jam ini")
    a = p.parse_args()

    daftar = [a.sel] if a.sel else KODE_SEL
    batas = pd.Timestamp(a.batas) if a.batas else None

    with bd.koneksi() as sambungan:
        id_pengguna = None
        pemicu = "penjadwal"
        if a.pengguna:
            with sambungan.cursor() as k:
                k.execute("SELECT id_pengguna FROM pengguna WHERE username=%s",
                          (a.pengguna,))
                b = k.fetchone()
            if not b:
                print(f"Pengguna '{a.pengguna}' tidak ada di tabel PENGGUNA.")
                return 1
            id_pengguna, pemicu = b["id_pengguna"], "manual"

        hasil = jalankan_siklus(sambungan, daftar, a.simpan, batas,
                                pemicu, id_pengguna)
        if a.simpan:
            sambungan.commit()
        else:
            print("\nMode coba-coba: tidak ada yang ditulis. "
                  "Tambahkan --simpan untuk menulis.")

    return 1 if hasil["gagal"] else 0


if __name__ == "__main__":
    sys.exit(main())
