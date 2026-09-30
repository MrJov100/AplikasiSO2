"""Akses PostgreSQL: membaca pengamatan dan menulis prediksi.

Inilah jalur utama menurut naskah Subbab 2.1 — "sistem membaca tiga pengamatan
terakhir dari basis data". Penarikan langsung ke Open-Meteo hanya jaring
pengaman, dan tidak dipakai di berkas ini.
"""
from contextlib import contextmanager

import pandas as pd
import psycopg
from psycopg.rows import dict_row

from konfigurasi import KOLOM_DB_KE_MODEL, LAGS, PG, VERSI_MODEL


@contextmanager
def koneksi():
    """Buka satu koneksi ke basis data dan pastikan ditutup kembali."""
    with psycopg.connect(**PG, row_factory=dict_row) as sambungan:
        yield sambungan


# Kekangan uk_pengamatan_lokasi_waktu (id_lokasi, waktu) sekaligus menjadi indeks
# yang melayani kueri ini. Rencana eksekusinya Index Scan Backward, bukan Seq Scan.
SQL_TIGA_TERAKHIR = """
SELECT p.id_pengamatan, p.waktu, p.so2, p.suhu, p.kelembapan, p.titik_embun,
       p.curah_hujan, p.tekanan_permukaan, p.tutupan_awan,
       p.kecepatan_angin, p.arah_angin
FROM   pengamatan p
JOIN   lokasi l ON l.id_lokasi = p.id_lokasi
WHERE  l.kode_sel = %(kode)s
  -- Yang dikeluarkan dari pembentukan lag HANYA baris berstatus
  -- 'dikecualikan', yaitu keputusan admin. Baris 'anomali' tetap dipakai:
  -- naskah Subbab 2.1 menyebut nilai tidak wajar "ditandai untuk ditinjau
  -- oleh admin", bukan langsung dibuang. Membuang otomatis juga akan
  -- menghentikan prediksi tiga jam setiap kali satu baris tertandai.
  AND  p.status <> 'dikecualikan'
  AND  (%(batas)s::timestamp IS NULL OR p.waktu <= %(batas)s::timestamp)
ORDER  BY p.waktu DESC
LIMIT  %(jumlah)s
"""


def ambil_pengamatan_terakhir(sambungan, kode_sel, batas_waktu=None, jumlah=None):
    """Baca beberapa pengamatan terakhir satu sel grid dari basis data.

    Return: (tabel, id_per_waktu)
      tabel        DataFrame berindeks waktu, nama kolomnya sudah diterjemahkan
                   ke nama yang dipakai berkas model
      id_per_waktu dict {waktu: id_pengamatan}, dibutuhkan untuk kunci asing
                   id_pengamatan_t1, t2, dan t3 pada tabel PREDIKSI
    """
    if jumlah is None:
        jumlah = len(LAGS)

    with sambungan.cursor() as kursor:
        kursor.execute(SQL_TIGA_TERAKHIR,
                       {"kode": kode_sel, "batas": batas_waktu, "jumlah": jumlah})
        baris = kursor.fetchall()

    if not baris:
        raise RuntimeError(f"{kode_sel}: tidak ada pengamatan pada rentang itu")

    baris = list(reversed(baris))          # dari kueri urutannya menurun
    id_per_waktu = {pd.Timestamp(b["waktu"]): b["id_pengamatan"] for b in baris}

    tabel = pd.DataFrame([
        {"time": pd.Timestamp(b["waktu"]),
         **{nama_model: float(b[nama_db]) for nama_db, nama_model in KOLOM_DB_KE_MODEL.items()}}
        for b in baris
    ])
    return tabel.sort_values("time").set_index("time"), id_per_waktu


# ON CONFLICT menjawab persoalan prediksi kembar: bila arsip Open-Meteo belum
# maju di antara dua jalan penjadwal, jam target yang sama bisa dihasilkan dua
# kali. Kekangan uk_prediksi_lokasi_waktu mencegah barisnya berganda, dan baris
# yang ada diperbarui dengan hasil terbaru.
SQL_SIMPAN_PREDIKSI = """
INSERT INTO prediksi (
    id_lokasi, waktu_prediksi, waktu_dasar,
    id_pengamatan_t1, id_pengamatan_t2, id_pengamatan_t3,
    nilai_xgboost, nilai_random_forest, nilai_so2,
    skenario, versi_model)
SELECT l.id_lokasi, %(waktu_prediksi)s, %(waktu_dasar)s,
       %(t1)s, %(t2)s, %(t3)s,
       %(xgboost)s, %(random_forest)s, %(so2)s,
       %(skenario)s, %(versi_model)s
FROM   lokasi l WHERE l.kode_sel = %(kode)s
ON CONFLICT (id_lokasi, waktu_prediksi) DO UPDATE SET
    waktu_dasar         = EXCLUDED.waktu_dasar,
    id_pengamatan_t1    = EXCLUDED.id_pengamatan_t1,
    id_pengamatan_t2    = EXCLUDED.id_pengamatan_t2,
    id_pengamatan_t3    = EXCLUDED.id_pengamatan_t3,
    nilai_xgboost       = EXCLUDED.nilai_xgboost,
    nilai_random_forest = EXCLUDED.nilai_random_forest,
    nilai_so2           = EXCLUDED.nilai_so2,
    versi_model         = EXCLUDED.versi_model,
    dibuat_pada         = (now() AT TIME ZONE 'Asia/Jakarta')
RETURNING id_prediksi, nilai_so2, kategori, melampaui_baku_mutu, rasio_baku_mutu
"""


def simpan_prediksi(sambungan, kode_sel, waktu_prediksi, waktu_dasar,
                    id_lag, hasil, skenario=2, versi_model=VERSI_MODEL):
    """Tulis satu baris prediksi, perbarui bila jam target itu sudah ada.

    id_lag adalah daftar tiga id_pengamatan berurutan t-1, t-2, t-3.

    Kolom kategori, melampaui_baku_mutu, rasio_baku_mutu, dan selisih TIDAK
    dikirim: keempatnya generated column yang dihitung basis data dari nilai_so2.
    Nilainya dikembalikan lewat RETURNING supaya dapat dibandingkan dengan
    hitungan Python sebagai pemeriksaan silang.
    """
    with sambungan.cursor() as kursor:
        kursor.execute(SQL_SIMPAN_PREDIKSI, {
            "kode": kode_sel,
            "waktu_prediksi": waktu_prediksi.to_pydatetime(),
            "waktu_dasar": waktu_dasar.to_pydatetime(),
            "t1": id_lag[0], "t2": id_lag[1], "t3": id_lag[2],
            "xgboost": round(hasil["xgboost"], 2),
            "random_forest": round(hasil["random_forest"], 2),
            "so2": round(hasil["stacking"], 2),
            "skenario": skenario,
            "versi_model": versi_model,
        })
        return kursor.fetchone()


# ============================================================================
#  SIKLUS SINKRONISASI DAN UPSERT PENGAMATAN
# ============================================================================

SQL_MULAI_SIKLUS = """
INSERT INTO siklus_sinkronisasi (pemicu, id_pengguna, status)
VALUES (%(pemicu)s, %(id_pengguna)s, 'berjalan')
RETURNING id_siklus
"""

SQL_RINCIAN = """
INSERT INTO sinkronisasi_lokasi (
    id_siklus, id_lokasi, waktu_data_terakhir, jumlah_baris_masuk,
    jumlah_baris_diperbarui, jumlah_anomali, status, pesan_galat, durasi_ms)
SELECT %(id_siklus)s, l.id_lokasi, %(waktu_terakhir)s, 0, 0, 0,
       %(status)s, %(pesan)s, 0
FROM   lokasi l WHERE l.kode_sel = %(kode)s
RETURNING id_sinkronisasi
"""

SQL_PERBARUI_RINCIAN = """
UPDATE sinkronisasi_lokasi
SET    waktu_data_terakhir      = %(waktu_terakhir)s,
       jumlah_baris_masuk       = %(masuk)s,
       jumlah_baris_diperbarui  = %(diperbarui)s,
       jumlah_anomali           = %(anomali)s,
       status                   = %(status)s,
       pesan_galat              = %(pesan)s,
       durasi_ms                = %(durasi)s
WHERE  id_sinkronisasi = %(id_sinkronisasi)s
"""

SQL_SELESAI_SIKLUS = """
UPDATE siklus_sinkronisasi
SET    waktu_selesai   = (now() AT TIME ZONE 'Asia/Jakarta'),
       status          = %(status)s,
       jumlah_berhasil = %(berhasil)s,
       jumlah_gagal    = %(gagal)s
WHERE  id_siklus = %(id_siklus)s
"""

# xmax = 0 hanya benar untuk baris yang baru disisipkan; baris hasil DO UPDATE
# membawa xmax bukan nol. Itu cara membedakan sisip dan perbarui dalam satu
# pernyataan.
#
# Kolom status dan alasan_anomali TIDAK ditimpa bila status yang tersimpan
# 'dikecualikan'. Nilai itu hanya pernah disetel admin lewat KOREKSI_PENGAMATAN,
# dan penarikan berkala tidak boleh menghapus keputusan manusia. Status
# 'anomali' boleh dihitung ulang karena itu keputusan sistem.
SQL_UPSERT_PENGAMATAN = """
INSERT INTO pengamatan (
    id_lokasi, waktu, id_sinkronisasi, so2, so2_mentah, suhu, kelembapan,
    titik_embun, curah_hujan, tekanan_permukaan, tutupan_awan,
    kecepatan_angin, arah_angin, status, alasan_anomali, diperbarui_pada)
VALUES (
    %(id_lokasi)s, %(waktu)s, %(id_sinkronisasi)s, %(so2)s, %(so2_mentah)s,
    %(suhu)s, %(kelembapan)s, %(titik_embun)s, %(curah_hujan)s,
    %(tekanan_permukaan)s, %(tutupan_awan)s, %(kecepatan_angin)s,
    %(arah_angin)s, %(status)s, %(alasan_anomali)s,
    (now() AT TIME ZONE 'Asia/Jakarta'))
ON CONFLICT (id_lokasi, waktu) DO UPDATE SET
    id_sinkronisasi   = EXCLUDED.id_sinkronisasi,
    so2               = EXCLUDED.so2,
    so2_mentah        = EXCLUDED.so2_mentah,
    suhu              = EXCLUDED.suhu,
    kelembapan        = EXCLUDED.kelembapan,
    titik_embun       = EXCLUDED.titik_embun,
    curah_hujan       = EXCLUDED.curah_hujan,
    tekanan_permukaan = EXCLUDED.tekanan_permukaan,
    tutupan_awan      = EXCLUDED.tutupan_awan,
    kecepatan_angin   = EXCLUDED.kecepatan_angin,
    arah_angin        = EXCLUDED.arah_angin,
    status            = CASE WHEN pengamatan.status = 'dikecualikan'
                             THEN pengamatan.status ELSE EXCLUDED.status END,
    alasan_anomali    = CASE WHEN pengamatan.status = 'dikecualikan'
                             THEN pengamatan.alasan_anomali
                             ELSE EXCLUDED.alasan_anomali END,
    diperbarui_pada   = (now() AT TIME ZONE 'Asia/Jakarta')
RETURNING (xmax = 0) AS disisipkan
"""

SQL_SO2_SEBELUM = """
SELECT p.so2
FROM   pengamatan p JOIN lokasi l ON l.id_lokasi = p.id_lokasi
WHERE  l.kode_sel = %(kode)s AND p.waktu = %(waktu)s
"""

SQL_ID_LOKASI = "SELECT id_lokasi FROM lokasi WHERE kode_sel = %(kode)s"


def id_lokasi(sambungan, kode_sel):
    with sambungan.cursor() as k:
        k.execute(SQL_ID_LOKASI, {"kode": kode_sel})
        b = k.fetchone()
    if not b:
        raise RuntimeError(f"Sel {kode_sel} tidak ada di tabel LOKASI")
    return b["id_lokasi"]


def so2_pada(sambungan, kode_sel, waktu):
    """Nilai SO2 satu jam tertentu, atau None. Dipakai lapis 5 untuk jam pertama."""
    with sambungan.cursor() as k:
        k.execute(SQL_SO2_SEBELUM, {"kode": kode_sel, "waktu": waktu})
        b = k.fetchone()
    return float(b["so2"]) if b else None


def mulai_siklus(sambungan, pemicu="penjadwal", id_pengguna=None):
    with sambungan.cursor() as k:
        k.execute(SQL_MULAI_SIKLUS, {"pemicu": pemicu, "id_pengguna": id_pengguna})
        return k.fetchone()["id_siklus"]


def buka_rincian(sambungan, id_siklus, kode_sel):
    with sambungan.cursor() as k:
        k.execute(SQL_RINCIAN, {"id_siklus": id_siklus, "kode": kode_sel,
                                "waktu_terakhir": None, "status": "gagal",
                                "pesan": "belum selesai"})
        return k.fetchone()["id_sinkronisasi"]


def tutup_rincian(sambungan, id_sinkronisasi, waktu_terakhir, masuk, diperbarui,
                  anomali, status, pesan, durasi):
    with sambungan.cursor() as k:
        k.execute(SQL_PERBARUI_RINCIAN, {
            "id_sinkronisasi": id_sinkronisasi, "waktu_terakhir": waktu_terakhir,
            "masuk": masuk, "diperbarui": diperbarui, "anomali": anomali,
            "status": status, "pesan": pesan, "durasi": durasi})


def selesaikan_siklus(sambungan, id_siklus, berhasil, gagal):
    status = ("berhasil" if gagal == 0 else "gagal" if berhasil == 0 else "sebagian")
    with sambungan.cursor() as k:
        k.execute(SQL_SELESAI_SIKLUS, {"id_siklus": id_siklus, "status": status,
                                       "berhasil": berhasil, "gagal": gagal})
    return status


def upsert_pengamatan(sambungan, baris):
    """Sisipkan atau perbarui satu baris pengamatan.

    Return: True bila baris baru disisipkan, False bila baris lama diperbarui.
    """
    with sambungan.cursor() as k:
        k.execute(SQL_UPSERT_PENGAMATAN, baris)
        return bool(k.fetchone()["disisipkan"])


# ============================================================================
#  PERLINDUNGAN NILAI YANG DIKOREKSI ADMIN
# ============================================================================

# Baris yang nilainya pernah diubah admin lewat tindakan 'ubah_nilai' TIDAK
# boleh ditimpa penarikan berkala. Tanpa ini, koreksi admin akan lenyap pada
# siklus berikutnya — justru pada jendela tiga hari terakhir, yaitu jam-jam yang
# paling mungkin sedang ditinjau.
SQL_JAM_DIKOREKSI = """
SELECT DISTINCT p.waktu
FROM   koreksi_pengamatan k
JOIN   pengamatan p ON p.id_pengamatan = k.id_pengamatan
JOIN   lokasi l     ON l.id_lokasi = p.id_lokasi
WHERE  l.kode_sel = %(kode)s
  AND  k.tindakan = 'ubah_nilai'
  AND  p.waktu >= %(sejak)s
"""


def jam_dikoreksi(sambungan, kode_sel, sejak):
    """Himpunan jam yang nilainya pernah dikoreksi admin, sejak waktu tertentu."""
    with sambungan.cursor() as k:
        k.execute(SQL_JAM_DIKOREKSI, {"kode": kode_sel, "sejak": sejak})
        return {b["waktu"] for b in k.fetchall()}


# ============================================================================
#  PENGISIAN NILAI AKTUAL PADA PREDIKSI
# ============================================================================

# Satu pernyataan berbasis himpunan, bukan pengulangan per baris. Indeks parsial
# ix_prediksi_aktual_kosong dipasang sejak Fase 2 khusus untuk kueri ini.
#
# Pengamatan berstatus 'dikecualikan' TETAP diisi supaya Halaman Riwayat Prediksi
# menampilkan nilainya. Yang menyaringnya adalah kueri metrik di bawah, bukan
# pengisian ini — dengan begitu tidak ada informasi yang hilang sementara
# MAE/RMSE operasional tetap bersih.
SQL_ISI_AKTUAL = """
UPDATE prediksi p
SET    nilai_aktual = o.so2
FROM   pengamatan o
WHERE  o.id_lokasi = p.id_lokasi
  AND  o.waktu     = p.waktu_prediksi
  AND  p.nilai_aktual IS NULL
RETURNING p.id_prediksi, p.id_lokasi, p.waktu_prediksi,
          p.nilai_so2, p.nilai_aktual, p.selisih, o.status AS status_pengamatan
"""

SQL_PREDIKSI_MENUNGGU = """
SELECT count(*) AS n, min(waktu_prediksi) AS paling_lama
FROM   prediksi WHERE nilai_aktual IS NULL
"""

# Ketelitian operasional untuk Bab 4. Baseline persistensi memakai SO2 pada t-1,
# diambil lewat kunci asing id_pengamatan_t1 — itulah gunanya menyimpan ketiga
# kunci asing lag pada tabel PREDIKSI.
SQL_KETELITIAN = """
SELECT count(*)                                                            AS n,
       round(avg(abs(p.nilai_aktual - p.nilai_so2)), 4)                    AS mae_stacking,
       round(sqrt(avg(power(p.nilai_aktual - p.nilai_so2, 2))), 4)         AS rmse_stacking,
       round(avg(abs(p.nilai_aktual - p.nilai_xgboost)), 4)                AS mae_xgboost,
       round(sqrt(avg(power(p.nilai_aktual - p.nilai_xgboost, 2))), 4)     AS rmse_xgboost,
       round(avg(abs(p.nilai_aktual - p.nilai_random_forest)), 4)          AS mae_rf,
       round(sqrt(avg(power(p.nilai_aktual - p.nilai_random_forest, 2))), 4) AS rmse_rf,
       round(avg(abs(p.nilai_aktual - t1.so2)), 4)                         AS mae_persistensi,
       round(sqrt(avg(power(p.nilai_aktual - t1.so2, 2))), 4)              AS rmse_persistensi,
       -- Cakupan. MAE dan RMSE adalah rerata berjalan: nilainya bergeser tiap
       -- kali satu baris bertambah. Tanpa keterangan rentang dan jam yang
       -- tercakup, angka yang dikutip Bab 4 tidak dapat direproduksi, dan
       -- lubang cakupan jam (mis. dini hari belum pernah tersampel) tidak
       -- terlihat sama sekali dari angka tunggal.
       min(p.waktu_prediksi)                                               AS jam_awal,
       max(p.waktu_prediksi)                                               AS jam_akhir,
       count(DISTINCT p.waktu_prediksi)                                    AS jam_berbeda,
       array_agg(DISTINCT extract(hour from p.waktu_prediksi)::int
                 ORDER BY extract(hour from p.waktu_prediksi)::int)        AS jam_tercakup
FROM   prediksi p
JOIN   pengamatan o  ON o.id_lokasi = p.id_lokasi AND o.waktu = p.waktu_prediksi
JOIN   pengamatan t1 ON t1.id_pengamatan = p.id_pengamatan_t1
WHERE  p.nilai_aktual IS NOT NULL
  AND  o.status <> 'dikecualikan'
  AND  p.versi_model = %(versi)s
"""


def isi_nilai_aktual(sambungan):
    """Isi nilai_aktual untuk prediksi yang jam targetnya sudah ada pengamatannya.

    Return: daftar baris yang terisi.
    """
    with sambungan.cursor() as k:
        k.execute(SQL_ISI_AKTUAL)
        return k.fetchall()


def prediksi_menunggu(sambungan):
    with sambungan.cursor() as k:
        k.execute(SQL_PREDIKSI_MENUNGGU)
        return k.fetchone()


def ketelitian_operasional(sambungan, versi_model=VERSI_MODEL):
    with sambungan.cursor() as k:
        k.execute(SQL_KETELITIAN, {"versi": versi_model})
        return k.fetchone()
