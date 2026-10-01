"""Tujuh repositori — lapisan Repositori pada Class Diagram (Gambar 4a).

Hanya repositori yang menyentuh SQL. Kelas layanan memanggil repositori, tidak
pernah menulis kueri sendiri.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from konfigurasi import VERSI_MODEL                        # noqa: E402


class LokasiRepository:
    def semua(self, s):
        with s.cursor() as k:
            k.execute("""
                SELECT kode_sel, nama, wilayah_administratif, lintang, bujur,
                       elevasi, karakteristik, urutan_tampil
                FROM   lokasi ORDER BY urutan_tampil""")
            return k.fetchall()

    def cari(self, s, kode_sel):
        with s.cursor() as k:
            k.execute("SELECT * FROM lokasi WHERE kode_sel = %s", (kode_sel,))
            return k.fetchone()


class PengamatanRepository:
    def riwayat(self, s, kode_sel, jam):
        """Deret SO2 per jam untuk grafik. Baris dikecualikan tidak ditampilkan."""
        with s.cursor() as k:
            k.execute("""
                SELECT p.waktu, p.so2, p.status
                FROM   pengamatan p JOIN lokasi l ON l.id_lokasi = p.id_lokasi
                WHERE  l.kode_sel = %s AND p.status <> 'dikecualikan'
                ORDER  BY p.waktu DESC LIMIT %s""", (kode_sel, jam))
            return list(reversed(k.fetchall()))

    def terakhir(self, s, kode_sel):
        with s.cursor() as k:
            k.execute("""
                SELECT p.waktu, p.so2
                FROM   pengamatan p JOIN lokasi l ON l.id_lokasi = p.id_lokasi
                WHERE  l.kode_sel = %s AND p.status <> 'dikecualikan'
                ORDER  BY p.waktu DESC LIMIT 1""", (kode_sel,))
            return k.fetchone()

    def ringkasan_per_sel(self, s):
        with s.cursor() as k:
            k.execute("""
                SELECT l.kode_sel, l.nama, l.urutan_tampil,
                       max(p.waktu)                                   AS waktu_data_terakhir,
                       count(*)                                       AS jumlah_pengamatan,
                       count(*) FILTER (WHERE p.status <> 'sah')      AS jumlah_anomali
                FROM   lokasi l LEFT JOIN pengamatan p ON p.id_lokasi = l.id_lokasi
                GROUP  BY l.kode_sel, l.nama, l.urutan_tampil
                ORDER  BY l.urutan_tampil""")
            return k.fetchall()

    def daftar_anomali(self, s, batas=200):
        with s.cursor() as k:
            k.execute("""
                SELECT p.id_pengamatan, l.kode_sel, p.waktu, p.so2, p.suhu,
                       p.kelembapan, p.titik_embun, p.curah_hujan,
                       p.tekanan_permukaan, p.tutupan_awan, p.kecepatan_angin,
                       p.arah_angin, p.status, p.alasan_anomali
                FROM   pengamatan p JOIN lokasi l ON l.id_lokasi = p.id_lokasi
                WHERE  p.status <> 'sah'
                ORDER  BY p.waktu DESC LIMIT %s""", (batas,))
            return k.fetchall()

    def cari(self, s, id_pengamatan):
        with s.cursor() as k:
            k.execute("""
                SELECT p.*, l.kode_sel FROM pengamatan p
                JOIN   lokasi l ON l.id_lokasi = p.id_lokasi
                WHERE  p.id_pengamatan = %s""", (id_pengamatan,))
            return k.fetchone()

    def ubah_status(self, s, id_pengamatan, status, alasan):
        """Mengganti hapus fisik. Penghapusan memutus pembentukan lag t-1..t-3."""
        with s.cursor() as k:
            k.execute("""
                UPDATE pengamatan
                SET    status = %s, alasan_anomali = %s,
                       diperbarui_pada = (now() AT TIME ZONE 'Asia/Jakarta')
                WHERE  id_pengamatan = %s
                RETURNING id_pengamatan, status, alasan_anomali""",
                      (status, alasan, id_pengamatan))
            return k.fetchone()

    def ubah_nilai(self, s, id_pengamatan, kolom, nilai_baru):
        if kolom not in ("so2", "suhu", "kelembapan", "titik_embun", "curah_hujan",
                         "tekanan_permukaan", "tutupan_awan", "kecepatan_angin",
                         "arah_angin"):
            raise ValueError(f"Kolom tidak dikenal: {kolom}")
        with s.cursor() as k:
            # Nama kolom tidak bisa diparameterkan; karena itu disaring dengan
            # daftar putih di atas, bukan disisipkan langsung dari masukan.
            k.execute(f"""
                UPDATE pengamatan
                SET    {kolom} = %s,
                       diperbarui_pada = (now() AT TIME ZONE 'Asia/Jakarta')
                WHERE  id_pengamatan = %s
                RETURNING id_pengamatan, {kolom} AS nilai""",
                      (nilai_baru, id_pengamatan))
            return k.fetchone()


class PrediksiRepository:
    def terkini(self, s, kode_sel=None):
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

    def riwayat(self, s, kode_sel=None, batas=200, hanya_terisi=False,
                versi_model=VERSI_MODEL):
        """Baris riwayat prediksi, beserta penanda apakah ikut dihitung.

        Kolom `dihitung` memakai syarat yang SAMA PERSIS dengan SQL_KETELITIAN
        (nilai aktual ada, versi model produksi, pengamatan tidak dikecualikan),
        dan sengaja dihitung di SQL, bukan di peramban. Kalau syaratnya ditulis
        ulang di sisi antarmuka, suatu saat keduanya akan berbeda dan halaman
        akan menandai baris yang sebenarnya ikut dihitung, atau sebaliknya.

        `sebab_tidak_dihitung` bernilai NULL untuk baris yang ikut dihitung
        maupun untuk baris yang nilai aktualnya memang belum tiba — yang
        terakhir bukan pengecualian, hanya belum waktunya.
        """
        with s.cursor() as k:
            k.execute("""
                SELECT p.id_prediksi, l.kode_sel, l.nama AS nama_lokasi,
                       p.waktu_prediksi, p.waktu_dasar, p.nilai_so2,
                       p.nilai_xgboost, p.nilai_random_forest, p.kategori,
                       p.melampaui_baku_mutu, p.rasio_baku_mutu, p.nilai_aktual,
                       p.selisih, p.versi_model, p.dibuat_pada,
                       (p.nilai_aktual IS NOT NULL
                        AND p.versi_model = %(versi)s
                        AND coalesce(o.status, '') <> 'dikecualikan')  AS dihitung,
                       CASE
                         WHEN p.nilai_aktual IS NULL          THEN NULL
                         WHEN p.versi_model <> %(versi)s      THEN 'versi uji'
                         WHEN o.status = 'dikecualikan'       THEN 'pengamatan dikecualikan'
                       END                                            AS sebab_tidak_dihitung
                FROM   prediksi p
                JOIN   lokasi l      ON l.id_lokasi = p.id_lokasi
                LEFT JOIN pengamatan o ON o.id_lokasi = p.id_lokasi
                                      AND o.waktu     = p.waktu_prediksi
                WHERE  (%(sel)s::varchar IS NULL OR l.kode_sel = %(sel)s::varchar)
                  AND  (NOT %(terisi)s OR p.nilai_aktual IS NOT NULL)
                ORDER  BY p.waktu_prediksi DESC, l.urutan_tampil
                LIMIT  %(batas)s""",
                {"sel": kode_sel, "terisi": hanya_terisi, "batas": batas,
                 "versi": versi_model})
            return k.fetchall()


class PenggunaRepository:
    def cari_username(self, s, username):
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
        with s.cursor() as k:
            k.execute("""
                UPDATE pengguna
                SET    terakhir_masuk = (now() AT TIME ZONE 'Asia/Jakarta')
                WHERE  id_pengguna = %s""", (id_pengguna,))

    def ubah_nama(self, s, id_pengguna, nama_lengkap):
        with s.cursor() as k:
            k.execute("""
                UPDATE pengguna SET nama_lengkap = %s
                WHERE  id_pengguna = %s
                RETURNING id_pengguna, username, nama_lengkap, peran, aktif,
                          terakhir_masuk, dibuat_pada""",
                      (nama_lengkap, id_pengguna))
            return k.fetchone()

    def ubah_username(self, s, id_pengguna, username):
        """Mengganti username; pemanggil wajib memastikan belum terpakai."""
        with s.cursor() as k:
            k.execute("""
                UPDATE pengguna SET username = %s
                WHERE  id_pengguna = %s
                RETURNING id_pengguna, username, nama_lengkap, peran, aktif,
                          terakhir_masuk, dibuat_pada""",
                      (username, id_pengguna))
            return k.fetchone()

    def ubah_kata_sandi(self, s, id_pengguna, kata_sandi_hash):
        """Hanya hash yang masuk ke basis data; kata sandi polos tidak disimpan."""
        with s.cursor() as k:
            k.execute("""
                UPDATE pengguna SET kata_sandi_hash = %s
                WHERE  id_pengguna = %s""", (kata_sandi_hash, id_pengguna))


class SiklusSinkronisasiRepository:
    def terakhir(self, s, batas=20):
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
    def terakhir_per_sel(self, s):
        with s.cursor() as k:
            k.execute("""
                SELECT DISTINCT ON (l.kode_sel)
                       l.kode_sel, sl.waktu_data_terakhir, sl.status,
                       sl.pesan_galat, sl.jumlah_baris_masuk,
                       sl.jumlah_baris_diperbarui, sl.jumlah_anomali,
                       sl.durasi_ms, s.waktu_mulai
                FROM   sinkronisasi_lokasi sl
                JOIN   lokasi l ON l.id_lokasi = sl.id_lokasi
                JOIN   siklus_sinkronisasi s ON s.id_siklus = sl.id_siklus
                ORDER  BY l.kode_sel, s.waktu_mulai DESC""")
            return {b["kode_sel"]: b for b in k.fetchall()}


class KoreksiPengamatanRepository:
    def catat(self, s, id_pengamatan, id_pengguna, tindakan, kolom_diubah,
              nilai_lama, nilai_baru, alasan):
        with s.cursor() as k:
            k.execute("""
                INSERT INTO koreksi_pengamatan (
                    id_pengamatan, id_pengguna, tindakan, kolom_diubah,
                    nilai_lama, nilai_baru, alasan)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id_koreksi, waktu_koreksi""",
                      (id_pengamatan, id_pengguna, tindakan, kolom_diubah,
                       nilai_lama, nilai_baru, alasan))
            return k.fetchone()

    def riwayat(self, s, batas=100):
        with s.cursor() as k:
            k.execute("""
                SELECT kp.id_koreksi, kp.id_pengamatan, l.kode_sel,
                       p.waktu AS waktu_pengamatan, u.nama_lengkap,
                       kp.tindakan, kp.kolom_diubah, kp.nilai_lama,
                       kp.nilai_baru, kp.alasan, kp.waktu_koreksi
                FROM   koreksi_pengamatan kp
                JOIN   pengamatan p ON p.id_pengamatan = kp.id_pengamatan
                JOIN   lokasi l     ON l.id_lokasi = p.id_lokasi
                JOIN   pengguna u   ON u.id_pengguna = kp.id_pengguna
                ORDER  BY kp.waktu_koreksi DESC LIMIT %s""", (batas,))
            return k.fetchall()
