"""Satu siklus sinkronisasi: tarik Open-Meteo, upsert ke PENGAMATAN.

Dipanggil penjadwal setiap jam, atau dijalankan tangan:

    python segarkan_pengamatan.py                  # coba-coba, tidak menulis
    python segarkan_pengamatan.py --simpan
    python segarkan_pengamatan.py --sel G04 --simpan
    python segarkan_pengamatan.py --simpan --pengguna admin

- Seluruh jendela HARI_MUNDUR hari di-upsert, bukan hanya jam terbaru, karena
  arsip Open-Meteo masih merevisi jam-jam terakhir.
- Dengan ulang_hingga, sel yang gagal ditarik ulang tiap JEDA_ULANG detik
  sampai berhasil atau sampai ulang_hingga.
- Nilai disimpan apa adanya setelah pra-pemrosesan pelatihan (lihat
  penarikan.py); nilai mustahil ditolak kekangan CHECK basis data.
"""
import argparse
import sys
import time

from datetime import timedelta

import pandas as pd
import psycopg

import basis_data as bd
import penarikan as tarik
from konfigurasi import HARI_MUNDUR, KODE_SEL, SEL_GRID, ZONA

# Jeda sebelum sel yang gagal ditarik ulang.
JEDA_ULANG = 300


def _sekarang():
    """Jam dinding Jakarta tanpa zona waktu, sebanding dengan ulang_hingga."""
    return pd.Timestamp.now(tz=ZONA).tz_localize(None)


def jelaskan_galat(e):
    """Kalimat untuk admin tentang kegagalan satu sel."""
    if isinstance(e, tarik.GalatPenarikan):
        return str(e)
    if isinstance(e, psycopg.Error):
        return (f"Data sudah ditarik dari Open-Meteo, tetapi gagal disimpan ke "
                f"basis data ({type(e).__name__}): {e}")
    return f"Galat tak terduga ({type(e).__name__}): {e}"


def proses_sel(sambungan, kode_sel, id_siklus, simpan, batas_waktu=None):
    """Tarik dan simpan satu sel grid. Return dict ringkasan."""
    mulai = time.monotonic()
    lintang, bujur, elevasi = SEL_GRID[kode_sel]

    tabel, kisi = tarik.tarik_sel(lintang, bujur, elevasi, HARI_MUNDUR, batas_waktu)
    if tabel.empty:
        raise tarik.GalatPenarikan(
            "Open-Meteo belum menyediakan jam yang lengkap untuk data SO2 dan "
            "data cuaca sekaligus.")

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
                    segel_status=True, ulang_hingga=None, jeda_ulang=JEDA_ULANG):
    """Satu siklus penuh untuk beberapa sel. Dipakai CLI maupun penjadwal.

    Tanpa ulang_hingga, tidak melakukan commit; pemanggil yang memutuskan kapan
    menyimpan. Dengan ulang_hingga (jam Jakarta tanpa zona), sel yang gagal
    ditarik ulang tiap jeda_ulang detik selama putaran berikutnya masih mulai
    paling lambat ulang_hingga. Sebelum menunggu, hasil sementara di-commit
    supaya admin melihat siklus 'berjalan' beserta alasannya, dan supaya tidak
    ada transaksi yang terbuka selama jeda.

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

    berhasil = 0
    sisa = list(daftar)
    ulang_ke = 0
    while True:
        gagal_putaran = {}                    # kode -> (pesan, durasi_ms)
        for kode in sisa:
            mulai_sel = time.monotonic()
            try:
                # Tiap sel di savepoint-nya sendiri, bukan rollback(): rollback
                # membatalkan seluruh transaksi, termasuk baris siklus dari
                # mulai_siklus() yang belum di-commit, sehingga sinkronisasi
                # gagal tidak muncul di riwayat. Savepoint hanya membatalkan
                # sel itu.
                if simpan:
                    with sambungan.transaction():
                        r = proses_sel(sambungan, kode, id_siklus, simpan, batas)
                else:
                    r = proses_sel(sambungan, kode, id_siklus, simpan, batas)
                berhasil += 1
                cetak(f"{kode:<5}{r['baris']:>7}{r['masuk']:>7}{r['diperbarui']:>10}"
                      f"{r['durasi_ms']:>7}  {r['waktu_terakhir']}")
            except Exception as e:                      # noqa: BLE001
                pesan = jelaskan_galat(e)
                gagal_putaran[kode] = (pesan, int((time.monotonic() - mulai_sel) * 1000))
                cetak(f"{kode:<5}  GAGAL: {type(e).__name__}: {pesan}")

        # Masih ada waktu untuk satu putaran lagi?
        berikutnya = _sekarang() + timedelta(seconds=jeda_ulang)
        lanjut = bool(gagal_putaran) and ulang_hingga is not None \
            and berikutnya <= ulang_hingga
        if lanjut:
            tindak = f" Ditarik ulang otomatis pukul {berikutnya:%H.%M}."
        elif gagal_putaran and ulang_ke:
            tindak = (f" Sudah ditarik ulang {ulang_ke} kali tiap "
                      f"{jeda_ulang // 60} menit; dilanjutkan siklus berikutnya.")
        else:
            tindak = ""

        # Rincian dicatat sesudah savepoint dibatalkan, karena baris rincian
        # dari proses_sel() ikut hilang. Pencatatan ini juga di savepoint: satu
        # INSERT yang ditolak akan membatalkan seluruh transaksi dan semua
        # perintah berikutnya gagal dengan "InFailedSqlTransaction", padahal
        # selesaikan_siklus() di bawah masih harus menyegel status.
        if simpan:
            for kode, (pesan, durasi) in gagal_putaran.items():
                try:
                    with sambungan.transaction():
                        bd.catat_rincian_gagal(sambungan, id_siklus, kode,
                                               pesan + tindak, durasi)
                except Exception as e2:                 # noqa: BLE001
                    # Alasan kegagalan pencatatan ikut dicetak, bukan ditelan.
                    cetak(f"{'':<5}  (rincian galat {kode} tidak tercatat: "
                          f"{type(e2).__name__}: {e2})")

        if not lanjut:
            break

        if simpan:
            bd.selesaikan_tarikan(sambungan, id_siklus, berhasil, len(gagal_putaran))
            sambungan.commit()
        cetak(f"\n{len(gagal_putaran)} sel gagal ({', '.join(gagal_putaran)}). "
              f"Penarikan ulang ke-{ulang_ke + 1} pukul {berikutnya:%H.%M}.\n")
        time.sleep(jeda_ulang)
        ulang_ke += 1
        sisa = list(gagal_putaran)

    gagal = len(gagal_putaran)
    galat = list(dict.fromkeys(p for p, _ in gagal_putaran.values()))[:3]

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
            "gagal": gagal, "galat_penarikan": galat, "ulang": ulang_ke}


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
