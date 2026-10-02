"""Satu siklus sinkronisasi: tarik Open-Meteo, validasi, upsert ke PENGAMATAN.

Inilah inti Fase 3b tanpa penjadwalnya. Dijalankan tangan dulu, nanti dipanggil
APScheduler setiap jam.

    python segarkan_pengamatan.py                  # coba-coba, tidak menulis
    python segarkan_pengamatan.py --simpan
    python segarkan_pengamatan.py --sel G04 --simpan
    python segarkan_pengamatan.py --simpan --pengguna admin

MENGAPA SELURUH JENDELA DI-UPSERT, BUKAN HANYA JAM TERBARU

Arsip Open-Meteo masih berubah untuk jam-jam terakhir: nilai yang ditarik
sebelum sebuah run selesai adalah prakiraan, dan diganti analisis kemudian.
Pemeriksaan 29 September pada G04 memperlihatkan batasnya jatuh tepat di 19.00
WIB, yaitu 12.00 UTC, batas run 12z. Karena itu setiap siklus menulis ulang
SELURUH jam yang ditarik (HARI_MUNDUR hari), bukan hanya jam terbaru. Kalau
tidak, prakiraan yang sudah usang akan menetap selamanya dan dipakai sebagai
lag.

KEPUTUSAN ADMIN TIDAK DITIMPA

Baris berstatus 'dikecualikan' hanya pernah disetel admin. Upsert mempertahankan
status dan alasannya. Status 'anomali' boleh dihitung ulang karena itu keputusan
sistem, bukan manusia.
"""
import argparse
import sys
import time

import pandas as pd

import basis_data as bd
import penarikan as tarik
import validasi as val
from konfigurasi import HARI_MUNDUR, KODE_SEL, SEL_GRID


def proses_sel(sambungan, kode_sel, id_siklus, simpan, batas_waktu=None):
    """Tarik, validasi, dan simpan satu sel grid. Return dict ringkasan."""
    mulai = time.monotonic()
    lintang, bujur, elevasi = SEL_GRID[kode_sel]

    tabel, kisi = tarik.tarik_sel(lintang, bujur, elevasi, HARI_MUNDUR, batas_waktu)
    if tabel.empty:
        raise RuntimeError("tidak ada jam yang lengkap di kedua sumber")

    idl = bd.id_lokasi(sambungan, kode_sel)
    id_sinkronisasi = bd.buka_rincian(sambungan, id_siklus, kode_sel) if simpan else None

    # Baris yang nilainya pernah dikoreksi admin lewat 'ubah_nilai' dilewati:
    # nilai yang tersimpan adalah milik admin, bukan milik sumber, dan menimpanya
    # akan menghapus koreksi itu tanpa jejak.
    dilindungi = bd.jam_dikoreksi(sambungan, kode_sel,
                                  tabel.index[0].to_pydatetime())

    # Lapis 5 membutuhkan SO2 jam sebelumnya. Untuk baris pertama jendela, jam
    # itu ada di basis data, bukan di tabel yang baru ditarik.
    sebelumnya = bd.so2_pada(sambungan, kode_sel,
                             (tabel.index[0] - pd.Timedelta(hours=1)).to_pydatetime())

    masuk = diperbarui = anomali = dilewati = 0
    contoh = []
    for waktu, b in tabel.iterrows():
        if waktu.to_pydatetime() in dilindungi:
            dilewati += 1
            # Lanjutkan rantai lonjakan memakai nilai yang TERSIMPAN, bukan nilai
            # dari API, karena nilai tersimpanlah yang dipakai model.
            tersimpan = bd.so2_pada(sambungan, kode_sel, waktu.to_pydatetime())
            sebelumnya = tersimpan if tersimpan is not None else sebelumnya
            continue

        baris = {k: (None if pd.isna(b[k]) else float(b[k]))
                 for k in tabel.columns}
        baris["waktu"] = waktu

        status, alasan = val.periksa(kode_sel, baris, sebelumnya)
        if status != "sah":
            anomali += 1
            if len(contoh) < 3:
                contoh.append(f"{waktu} {alasan}")
        sebelumnya = baris["so2"]

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
                "arah_angin": baris["arah_angin"],
                "status": status, "alasan_anomali": alasan})
            masuk += disisipkan
            diperbarui += not disisipkan

    durasi = int((time.monotonic() - mulai) * 1000)
    if simpan:
        bd.tutup_rincian(sambungan, id_sinkronisasi, tabel.index[-1].to_pydatetime(),
                         masuk, diperbarui, anomali, "berhasil", None, durasi)

    return {"kode_sel": kode_sel, "baris": len(tabel), "masuk": masuk,
            "diperbarui": diperbarui, "anomali": anomali, "dilewati": dilewati,
            "contoh": contoh, "waktu_terakhir": tabel.index[-1], "kisi": kisi,
            "durasi_ms": durasi}


def jalankan_siklus(sambungan, daftar=None, simpan=True, batas=None,
                    pemicu="penjadwal", id_pengguna=None, cetak=print,
                    segel_status=True):
    """Satu siklus penuh untuk beberapa sel. Dipakai CLI maupun penjadwal.

    Tidak melakukan commit; pemanggil yang memutuskan kapan menyimpan.

    segel_status=False menyisakan status siklus tetap 'berjalan', supaya
    pemanggil yang masih punya langkah lanjutan -- penjadwal, dengan langkah
    prediksi dan pengisian nilai aktual -- dapat menyetel status akhir sesudah
    semuanya selesai. Tanpa itu, siklus tersegel 'berhasil' di sini dan
    kegagalan langkah berikutnya tidak pernah terlihat di riwayat.
    """
    daftar = daftar or KODE_SEL
    id_siklus = bd.mulai_siklus(sambungan, pemicu, id_pengguna) if simpan else None
    if simpan:
        cetak(f"Siklus {id_siklus} dimulai (pemicu {pemicu})\n")

    cetak(f"{'sel':<5}{'baris':>7}{'sisip':>7}{'perbarui':>10}{'anomali':>9}"
          f"{'dilindungi':>12}{'ms':>7}  waktu terakhir")

    berhasil = gagal = total_anomali = total_dilewati = 0
    for kode in daftar:
        mulai_sel = time.monotonic()
        try:
            # Tiap sel ditulis di dalam savepoint-nya sendiri. Dulu di sini
            # dipakai sambungan.rollback(), yang membatalkan SELURUH transaksi
            # -- termasuk baris SIKLUS_SINKRONISASI yang baru dibuat
            # mulai_siklus() di atas, karena pemanggil belum commit. Akibatnya
            # sinkronisasi yang gagal tidak pernah muncul di tab "Riwayat
            # sinkronisasi": UPDATE penyegel status mengenai nol baris, dan
            # yang tersimpan hanyalah transaksi kosong. Savepoint membatalkan
            # tulisan sel yang gagal saja dan membiarkan baris siklus hidup.
            if simpan:
                with sambungan.transaction():
                    r = proses_sel(sambungan, kode, id_siklus, simpan, batas)
            else:
                r = proses_sel(sambungan, kode, id_siklus, simpan, batas)
            berhasil += 1
            total_anomali += r["anomali"]
            total_dilewati += r["dilewati"]
            cetak(f"{kode:<5}{r['baris']:>7}{r['masuk']:>7}{r['diperbarui']:>10}"
                  f"{r['anomali']:>9}{r['dilewati']:>12}{r['durasi_ms']:>7}"
                  f"  {r['waktu_terakhir']}")
            for c in r["contoh"]:
                cetak(f"       -> {c}")
        except Exception as e:                          # noqa: BLE001
            gagal += 1
            pesan = f"{type(e).__name__}: {e}"
            cetak(f"{kode:<5}  GAGAL: {pesan}")
            # Rincian per sel dicatat SESUDAH savepoint dibatalkan: baris
            # rincian yang dibuka proses_sel() ikut hilang bersama savepoint,
            # jadi alasan kegagalan harus ditulis ulang di luar lingkupnya.
            #
            # Pencatatan itu sendiri dibungkus savepoint lagi. Tanpa savepoint,
            # satu INSERT yang ditolak -- misalnya karena sel ini sudah punya
            # baris rincian -- akan membuat Postgres membatalkan SELURUH
            # transaksi, dan setiap perintah sesudahnya ditolak dengan
            # "InFailedSqlTransaction: current transaction is aborted". Pesan
            # itu hanya puing: galat aslinya sudah lewat dan tidak terbaca.
            # Savepoint menahan kerusakan di sini, sehingga selesaikan_siklus()
            # di bawah masih dapat menyegel status siklus.
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
                  f"({berhasil} berhasil, {gagal} gagal, {total_anomali} ditandai, "
                  f"{total_dilewati} dilindungi)")
        else:
            status = bd.selesaikan_tarikan(sambungan, id_siklus, berhasil, gagal)
            cetak(f"\nPenarikan siklus {id_siklus}: {status} "
                  f"({berhasil} berhasil, {gagal} gagal, {total_anomali} ditandai, "
                  f"{total_dilewati} dilindungi)")
    return {"id_siklus": id_siklus, "status": status, "berhasil": berhasil,
            "gagal": gagal, "anomali": total_anomali, "dilewati": total_dilewati}


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
            print(f"\nMode coba-coba: tidak ada yang ditulis. "
                  f"{hasil['anomali']} baris akan ditandai anomali. "
                  "Tambahkan --simpan untuk menulis.")

    return 1 if hasil["gagal"] else 0


if __name__ == "__main__":
    sys.exit(main())
