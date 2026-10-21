"""Tujuh repositori — lapisan Repositori.

Hanya repositori yang menyentuh SQL. Kelas layanan memanggil repositori, tidak
pernah menulis kueri sendiri.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from konfigurasi import VERSI_MODEL                        # noqa: E402


class LokasiRepository:
    """Akses tabel lokasi."""
    def semua(self, s):
        """Semua lokasi berurutan sesuai urutan tampil."""
        with s.cursor() as k:
            k.execute("""
                SELECT kode_sel, nama, wilayah_administratif, lintang, bujur,
                       elevasi, karakteristik, urutan_tampil
                FROM   lokasi ORDER BY urutan_tampil""")
            return k.fetchall()

    def cari(self, s, kode_sel):
        """Satu lokasi berdasarkan kode sel."""
        with s.cursor() as k:
            k.execute("SELECT * FROM lokasi WHERE kode_sel = %s", (kode_sel,))
            return k.fetchone()


class PengamatanRepository:
    """Akses tabel pengamatan (data SO2 dan meteorologi per jam)."""
    def riwayat(self, s, kode_sel, jam):
        """Deret SO2 per jam untuk grafik."""
        with s.cursor() as k:
            k.execute("""
                SELECT p.waktu, p.so2
                FROM   pengamatan p JOIN lokasi l ON l.id_lokasi = p.id_lokasi
                WHERE  l.kode_sel = %s
                ORDER  BY p.waktu DESC LIMIT %s""", (kode_sel, jam))
            return list(reversed(k.fetchall()))

    def terakhir(self, s, kode_sel):
        """Pengamatan terbaru satu sel."""
        with s.cursor() as k:
            k.execute("""
                SELECT p.waktu, p.so2
                FROM   pengamatan p JOIN lokasi l ON l.id_lokasi = p.id_lokasi
                WHERE  l.kode_sel = %s
                ORDER  BY p.waktu DESC LIMIT 1""", (kode_sel,))
            return k.fetchone()

    def terakhir_semua_sel(self, s):
        """Pengamatan terbaru SETIAP sel sekaligus, berkunci kode sel.

        Menggantikan pemanggilan terakhir() sekali per sel di dalam perulangan
        pada LayananPrediksi.semua_terkini() — sebelas kueri untuk satu
        permintaan beranda, pola N+1.

        LATERAL, BUKAN DISTINCT ON. Keduanya menghasilkan baris yang sama, tetapi
        rencana eksekusinya berbeda jauh. DISTINCT ON (l.kode_sel) ... ORDER BY
        l.kode_sel, p.waktu DESC tidak dapat memakai uk_pengamatan_lokasi_waktu
        karena urutan yang dimintanya diawali kode_sel dari tabel lain: Postgres
        memilih Seq Scan atas seluruh 365 ribu baris pengamatan lalu mengurutkan
        di luar memori (external merge, ~12 MB) hanya untuk mengembalikan sepuluh
        baris — 303 ms, yaitu LEBIH LAMBAT daripada sebelas kueri yang
        digantinya.

        Bentuk LATERAL di bawah meminta sepuluh pencarian terpisah, masing-masing
        ORDER BY p.waktu DESC LIMIT 1 dengan id_lokasi tetap — persis bentuk yang
        dilayani indeks itu. Rencananya Index Scan Backward, 0,2 ms.
        """
        with s.cursor() as k:
            k.execute("""
                SELECT l.kode_sel, t.waktu, t.so2
                FROM   lokasi l
                CROSS  JOIN LATERAL (
                           SELECT p.waktu, p.so2
                           FROM   pengamatan p
                           WHERE  p.id_lokasi = l.id_lokasi
                           ORDER  BY p.waktu DESC
                           LIMIT  1) t""")
            return {b["kode_sel"]: b for b in k.fetchall()}

    def ringkasan_per_sel(self, s):
        """Waktu data terakhir dan jumlah pengamatan tiap sel."""
        with s.cursor() as k:
            k.execute("""
                SELECT l.kode_sel, l.nama, l.urutan_tampil,
                       max(p.waktu)                                   AS waktu_data_terakhir,
                       count(*)                                       AS jumlah_pengamatan
                FROM   lokasi l LEFT JOIN pengamatan p ON p.id_lokasi = l.id_lokasi
                GROUP  BY l.kode_sel, l.nama, l.urutan_tampil
                ORDER  BY l.urutan_tampil""")
            return k.fetchall()


class PrediksiRepository:
    """Akses tabel prediksi."""
    def terkini(self, s, kode_sel=None):
        """Prediksi terbaru per sel (atau satu sel bila kode diberikan), berurutan sesuai urutan tampil."""
        with s.cursor() as k:
            k.execute("""
                SELECT DISTINCT ON (l.kode_sel)
                       p.id_prediksi, l.kode_sel, l.nama AS nama_lokasi,
                       p.waktu_prediksi, p.waktu_dasar, p.nilai_so2,
                       p.nilai_xgboost, p.nilai_random_forest, p.kategori,
                       p.melampaui_baku_mutu, p.rasio_baku_mutu, p.nilai_aktual,
                       p.selisih, p.versi_model, p.dibuat_pada, l.urutan_tampil
                FROM   prediksi p JOIN lokasi l ON l.id_lokasi = p.id_lokasi
                WHERE  (%s::varchar IS NULL OR l.kode_sel = %s::varchar)
                ORDER  BY l.kode_sel, p.waktu_prediksi DESC""",
                      (kode_sel, kode_sel))
            baris = k.fetchall()
        return sorted(baris, key=lambda b: b["urutan_tampil"])

    def riwayat(self, s, kode_sel=None, halaman=1, per_halaman=10,
                hanya_terisi=False, versi_model=VERSI_MODEL):
        """Satu halaman baris riwayat prediksi beserta jumlah seluruh barisnya.

        Paginasi dilakukan di SQL (LIMIT/OFFSET), sehingga peramban hanya
        menerima baris untuk halaman yang sedang dibuka. Jumlah seluruh baris
        dihitung dengan syarat WHERE yang sama agar navigasi halaman tepat.
        Urutan diberi pemutus seri id_prediksi supaya OFFSET stabil: tanpa
        itu, baris dengan waktu dan sel yang sama dapat berpindah halaman.

        Kolom `dihitung` memakai syarat yang SAMA PERSIS dengan SQL_KETELITIAN
        (nilai aktual ada, versi model produksi),
        dan sengaja dihitung di SQL, bukan di peramban. Kalau syaratnya ditulis
        ulang di sisi antarmuka, suatu saat keduanya akan berbeda dan halaman
        akan menandai baris yang sebenarnya ikut dihitung, atau sebaliknya.

        `sebab_tidak_dihitung` bernilai NULL untuk baris yang ikut dihitung
        maupun untuk baris yang nilai aktualnya memang belum tiba — yang
        terakhir bukan pengecualian, hanya belum waktunya.
        """
        param = {"sel": kode_sel, "terisi": hanya_terisi, "versi": versi_model,
                 "batas": per_halaman, "lewati": (halaman - 1) * per_halaman}
        with s.cursor() as k:
            k.execute("""
                SELECT count(*) AS total
                FROM   prediksi p
                JOIN   lokasi l      ON l.id_lokasi = p.id_lokasi
                WHERE  (%(sel)s::varchar IS NULL OR l.kode_sel = %(sel)s::varchar)
                  AND  (NOT %(terisi)s OR p.nilai_aktual IS NOT NULL)
                  AND  p.versi_model = %(versi)s""", param)
            total = int(k.fetchone()["total"])
            k.execute("""
                SELECT p.id_prediksi, l.kode_sel, l.nama AS nama_lokasi,
                       p.waktu_prediksi, p.waktu_dasar, p.nilai_so2,
                       p.nilai_xgboost, p.nilai_random_forest, p.kategori,
                       p.melampaui_baku_mutu, p.rasio_baku_mutu, p.nilai_aktual,
                       p.selisih, p.versi_model, p.dibuat_pada,
                       (p.nilai_aktual IS NOT NULL
                        AND p.versi_model = %(versi)s)                AS dihitung,
                       CASE
                         WHEN p.nilai_aktual IS NULL          THEN NULL
                         WHEN p.versi_model <> %(versi)s      THEN 'versi uji'
                       END                                            AS sebab_tidak_dihitung
                FROM   prediksi p
                JOIN   lokasi l      ON l.id_lokasi = p.id_lokasi
                WHERE  (%(sel)s::varchar IS NULL OR l.kode_sel = %(sel)s::varchar)
                  AND  (NOT %(terisi)s OR p.nilai_aktual IS NOT NULL)
                  AND  p.versi_model = %(versi)s
                ORDER  BY p.waktu_prediksi DESC, l.urutan_tampil, p.id_prediksi
                LIMIT  %(batas)s OFFSET %(lewati)s""", param)
            return {"total": total, "baris": k.fetchall()}


class PenggunaRepository:
    """Akses tabel pengguna (admin)."""
    def cari_username(self, s, username):
        """Satu pengguna berdasarkan username, termasuk hash kata sandinya."""
        with s.cursor() as k:
            k.execute("""
                SELECT id_pengguna, username, kata_sandi_hash, nama_lengkap,
                       peran, aktif
                FROM   pengguna WHERE username = %s""", (username,))
            return k.fetchone()

    def cari_id(self, s, id_pengguna):
        """Data satu pengguna beserta hash kata sandinya.

        Dipakai Modul Profil Admin: rincian profil maupun pemeriksaan kata sandi
        lama saat admin menggantinya.
        """
        with s.cursor() as k:
            k.execute("""
                SELECT id_pengguna, username, kata_sandi_hash, nama_lengkap,
                       peran, aktif, terakhir_masuk, dibuat_pada
                FROM   pengguna WHERE id_pengguna = %s""", (id_pengguna,))
            return k.fetchone()

    def catat_masuk(self, s, id_pengguna):
        """Memperbarui waktu terakhir masuk pengguna."""
        with s.cursor() as k:
            k.execute("""
                UPDATE pengguna
                SET    terakhir_masuk = (now() AT TIME ZONE 'Asia/Jakarta')
                WHERE  id_pengguna = %s""", (id_pengguna,))


class SiklusSinkronisasiRepository:
    """Akses tabel siklus_sinkronisasi."""
    def terakhir(self, s, batas=20):
        """Siklus sinkronisasi terbaru beserta rincian jumlah langkahnya."""
        with s.cursor() as k:
            # to_jsonb(...)->>'...' membaca kolom rincian langkah tanpa
            # menyebutkan namanya di daftar SELECT, sehingga kueri tetap jalan
            # pada basis data yang belum dimigrasi (lihat
            # migrasi_kolom_langkah.py) dan bukan memunculkan UndefinedColumn.
            k.execute("""
                SELECT id_siklus, waktu_mulai, waktu_selesai, pemicu, status,
                       jumlah_berhasil, jumlah_gagal,
                       (to_jsonb(s)->>'prediksi_berhasil')::int AS prediksi_berhasil,
                       (to_jsonb(s)->>'prediksi_gagal')::int    AS prediksi_gagal,
                       (to_jsonb(s)->>'aktual_terisi')::int     AS aktual_terisi
                FROM   siklus_sinkronisasi s
                ORDER  BY waktu_mulai DESC LIMIT %s""", (batas,))
            return k.fetchall()


class SinkronisasiLokasiRepository:
    """Akses tabel sinkronisasi_lokasi (hasil sinkronisasi per sel)."""
    def terakhir_per_sel(self, s):
        """Hasil sinkronisasi terakhir tiap sel, dalam bentuk kamus berkunci kode sel."""
        with s.cursor() as k:
            k.execute("""
                SELECT DISTINCT ON (l.kode_sel)
                       l.kode_sel, sl.waktu_data_terakhir, sl.status,
                       sl.pesan_galat, sl.jumlah_baris_masuk,
                       sl.jumlah_baris_diperbarui,
                       sl.durasi_ms, s.waktu_mulai
                FROM   sinkronisasi_lokasi sl
                JOIN   lokasi l ON l.id_lokasi = sl.id_lokasi
                JOIN   siklus_sinkronisasi s ON s.id_siklus = sl.id_siklus
                ORDER  BY l.kode_sel, s.waktu_mulai DESC""")
            return {b["kode_sel"]: b for b in k.fetchall()}
