"""Enam layanan — lapisan Layanan pada Class Diagram (Gambar 4b).

Layanan memanggil repositori dan modul pendukung; tidak menulis SQL sendiri.
"""
import re
import sys
from datetime import timedelta
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import basis_data as bd                                   # noqa: E402
import jalankan_prediksi as jp                            # noqa: E402
import model as md                                        # noqa: E402
import segarkan_pengamatan as sp                          # noqa: E402
from api import repositori as repo                        # noqa: E402
from api import keamanan                                  # noqa: E402
from konfigurasi import (AMBANG_KATEGORI, BAKU_MUTU_1_JAM,       # noqa: E402
                         BATAS_KEMUTAKHIRAN_JAM, KODE_SEL, VERSI_MODEL)


def _kemutakhiran(waktu_terakhir):
    """Keterangan kemutakhiran data, dijanjikan naskah Subbab 2.1.1."""
    if waktu_terakhir is None:
        return {"waktu_data_terakhir": None, "tertinggal_jam": None,
                "mutakhir": False}
    sekarang = md.jam_sekarang()
    tertinggal = int((sekarang - pd.Timestamp(waktu_terakhir)) / pd.Timedelta(hours=1))
    return {"waktu_data_terakhir": waktu_terakhir,
            "tertinggal_jam": max(0, tertinggal),
            "mutakhir": tertinggal <= BATAS_KEMUTAKHIRAN_JAM}


class LayananLokasi:
    """Layanan informasi lokasi sel grid."""
    def __init__(self):
        """Menyiapkan repositori lokasi."""
        self.r = repo.LokasiRepository()

    def daftar(self, s):
        """Mengembalikan semua lokasi berurutan sesuai urutan tampil."""
        return self.r.semua(s)


class LayananAutentikasi:
    """Layanan masuk dan pengelolaan profil admin (nama, username, kata sandi)."""
    def __init__(self):
        """Menyiapkan repositori pengguna."""
        self.r = repo.PenggunaRepository()

    def masuk(self, s, username, kata_sandi):
        """Memverifikasi kredensial; mengembalikan data pengguna bila sah, None bila gagal."""
        p = self.r.cari_username(s, (username or "").strip().lower())
        # Pesan galat sengaja sama untuk username salah maupun kata sandi salah,
        # supaya tidak membocorkan username mana yang terdaftar.
        if not p or not p["aktif"]:
            return None
        if not keamanan.periksa_kata_sandi(kata_sandi, p["kata_sandi_hash"]):
            return None
        self.r.catat_masuk(s, p["id_pengguna"])
        s.commit()
        return p

    # ---------- Modul Profil Admin ----------
    # Rincian profil dibaca ulang dari basis data, bukan dari isi token: token
    # hanya menyimpan nama saat masuk, sehingga nama yang baru diganti akan
    # tertinggal bila dibaca dari sana.
    def profil(self, s, id_pengguna):
        """Membaca profil terkini admin dari basis data, tanpa hash kata sandi."""
        p = self.r.cari_id(s, id_pengguna)
        if not p:
            raise ValueError("Akun tidak ditemukan.")
        return self._tanpa_hash(p)

    def ubah_nama(self, s, id_pengguna, nama_lengkap):
        """Mengganti nama lengkap admin setelah memvalidasi panjangnya."""
        nama = (nama_lengkap or "").strip()
        if len(nama) < 3:
            raise ValueError("Nama lengkap minimal tiga karakter.")
        if len(nama) > 100:
            raise ValueError("Nama lengkap maksimal seratus karakter.")
        p = self.r.ubah_nama(s, id_pengguna, nama)
        if not p:
            raise ValueError("Akun tidak ditemukan.")
        s.commit()
        return self._tanpa_hash(p)

    def ubah_username(self, s, id_pengguna, username_baru, kata_sandi):
        """Mengganti username. Kata sandi diminta sebagai penegasan karena
        username adalah identitas untuk masuk."""
        p = self.r.cari_id(s, id_pengguna)
        if not p:
            raise ValueError("Akun tidak ditemukan.")
        if not keamanan.periksa_kata_sandi(kata_sandi, p["kata_sandi_hash"]):
            raise ValueError("Kata sandi salah.")

        # Kekangan ck_pengguna_username menuntut huruf kecil dan minimal empat
        # karakter; dinormalkan dan diperiksa di sini supaya pesan galatnya
        # jelas, bukan berupa galat kekangan dari basis data.
        baru = (username_baru or "").strip().lower()
        if len(baru) < 4:
            raise ValueError("Username minimal empat karakter.")
        if len(baru) > 50:
            raise ValueError("Username maksimal lima puluh karakter.")
        if not re.fullmatch(r"[a-z0-9._-]+", baru):
            raise ValueError("Username hanya boleh huruf kecil, angka, titik, "
                             "garis bawah, dan garis datar.")
        if baru == p["username"]:
            raise ValueError("Username baru sama dengan yang sekarang.")

        lain = self.r.cari_username(s, baru)
        if lain:
            raise ValueError("Username sudah dipakai akun lain.")

        hasil = self.r.ubah_username(s, id_pengguna, baru)
        s.commit()
        return self._tanpa_hash(hasil)

    def ubah_kata_sandi(self, s, id_pengguna, kata_sandi_lama, kata_sandi_baru):
        """Mengganti kata sandi admin setelah memeriksa kata sandi lama dan aturan kata sandi baru."""
        p = self.r.cari_id(s, id_pengguna)
        if not p:
            raise ValueError("Akun tidak ditemukan.")
        # Kata sandi lama wajib benar supaya sesi yang tertinggal terbuka pada
        # komputer bersama tidak bisa dipakai mengambil alih akun.
        if not keamanan.periksa_kata_sandi(kata_sandi_lama, p["kata_sandi_hash"]):
            raise ValueError("Kata sandi lama salah.")
        # Batas delapan karakter sama dengan buat_admin.py.
        if len(kata_sandi_baru or "") < 8:
            raise ValueError("Kata sandi baru minimal delapan karakter.")
        if kata_sandi_baru == kata_sandi_lama:
            raise ValueError("Kata sandi baru harus berbeda dari yang lama.")
        self.r.ubah_kata_sandi(s, id_pengguna,
                               keamanan.hash_kata_sandi(kata_sandi_baru))
        s.commit()

    @staticmethod
    def _tanpa_hash(p):
        """Hash kata sandi tidak boleh ikut keluar lewat API."""
        return {k: v for k, v in dict(p).items() if k != "kata_sandi_hash"}


class LayananPrediksi:
    """Layanan penyajian prediksi SO2 terkini beserta keterangan kemutakhiran datanya."""
    def __init__(self):
        """Menyiapkan repositori prediksi dan pengamatan."""
        self.r = repo.PrediksiRepository()
        self.rp = repo.PengamatanRepository()

    def terkini(self, s, kode_sel):
        """Prediksi terbaru satu sel, dengan status kemutakhiran dan SO2 aktual terakhir."""
        prediksi = self.r.terkini(s, kode_sel)
        terakhir = self.rp.terakhir(s, kode_sel)
        km = _kemutakhiran(terakhir["waktu"] if terakhir else None)
        pesan = None
        if not km["mutakhir"]:
            pesan = ("Data belum mutakhir, prediksi yang ditampilkan berasal "
                     "dari siklus sebelumnya.")
        return {"prediksi": prediksi[0] if prediksi else None,
                "kemutakhiran": km,
                "so2_terakhir": float(terakhir["so2"]) if terakhir else None,
                "pesan": pesan}

    def semua_terkini(self, s):
        """Prediksi terbaru seluruh sel, masing-masing dengan status kemutakhiran data."""
        prediksi = self.r.terkini(s, None)
        hasil = []
        for p in prediksi:
            terakhir = self.rp.terakhir(s, p["kode_sel"])
            hasil.append({**p, **{"kemutakhiran":
                                  _kemutakhiran(terakhir["waktu"] if terakhir else None)}})
        return hasil


class LayananVisualisasi:
    """Layanan data untuk grafik riwayat SO2."""
    def __init__(self):
        """Menyiapkan repositori pengamatan."""
        self.r = repo.PengamatanRepository()

    def riwayat(self, s, kode_sel, jam):
        """Deret SO2 per jam satu sel bersama baku mutu dan ambang kategori."""
        titik = self.r.riwayat(s, kode_sel, jam)
        return {"kode_sel": kode_sel, "jam": jam,
                "baku_mutu_satu_jam": BAKU_MUTU_1_JAM,
                "ambang_kategori": [{"batas": b, "nama": n}
                                    for b, n in AMBANG_KATEGORI],
                "titik": titik}


class LayananSinkronisasi:
    """Termasuk fungsi pemantauan; LayananMonitoring dilebur ke sini sesuai
    catatan rancangan Class Diagram agar satu controller berpasangan dengan
    satu layanan."""

    def __init__(self):
        """Menyiapkan repositori pengamatan, sinkronisasi, siklus, dan koreksi."""
        self.rp = repo.PengamatanRepository()
        self.rsl = repo.SinkronisasiLokasiRepository()
        self.rs = repo.SiklusSinkronisasiRepository()
        self.rk = repo.KoreksiPengamatanRepository()

    def status(self, s):
        """Ringkasan status data dan sinkronisasi tiap sel untuk Modul Monitoring."""
        ringkas = self.rp.ringkasan_per_sel(s)
        sinkron = self.rsl.terakhir_per_sel(s)
        hasil = []
        for b in ringkas:
            sk = sinkron.get(b["kode_sel"], {})
            hasil.append({
                "kode_sel": b["kode_sel"], "nama": b["nama"],
                **_kemutakhiran(b["waktu_data_terakhir"]),
                "jumlah_pengamatan": b["jumlah_pengamatan"],
                "jumlah_anomali": b["jumlah_anomali"],
                "sinkronisasi_terakhir": sk.get("waktu_mulai"),
                "status_sinkronisasi": sk.get("status"),
                "pesan_galat": sk.get("pesan_galat")})
        return hasil

    def siklus_terakhir(self, s, batas=20):
        """Siklus sinkronisasi terbaru, paling baru lebih dulu."""
        return self.rs.terakhir(s, batas)

    def anomali(self, s, batas=200):
        """Pengamatan yang berstatus bukan 'sah'."""
        return self.rp.daftar_anomali(s, batas)

    def riwayat_koreksi(self, s, batas=100):
        """Jejak audit koreksi admin terbaru."""
        return self.rk.riwayat(s, batas)

    def koreksi(self, s, id_pengguna, permintaan):
        """Catat tindakan admin atas satu pengamatan, sekaligus jejak auditnya."""
        p = self.rp.cari(s, permintaan.id_pengamatan)
        if not p:
            raise ValueError("Pengamatan tidak ditemukan")

        tindakan = permintaan.tindakan
        nilai_lama = None
        kolom = None

        if tindakan == "tandai_anomali":
            self.rp.ubah_status(s, p["id_pengamatan"], "anomali", permintaan.alasan[:100])
        elif tindakan == "kecualikan":
            self.rp.ubah_status(s, p["id_pengamatan"], "dikecualikan", permintaan.alasan[:100])
        elif tindakan == "pulihkan":
            self.rp.ubah_status(s, p["id_pengamatan"], "sah", None)
        elif tindakan == "ubah_nilai":
            kolom = permintaan.kolom_diubah
            if not kolom or permintaan.nilai_baru is None:
                raise ValueError("ubah_nilai memerlukan kolom_diubah dan nilai_baru")
            nilai_lama = float(p[kolom])
            self.rp.ubah_nilai(s, p["id_pengamatan"], kolom, permintaan.nilai_baru)
        else:
            raise ValueError(f"Tindakan tidak dikenal: {tindakan}")

        hasil = self.rk.catat(s, p["id_pengamatan"], id_pengguna, tindakan,
                              kolom, nilai_lama, permintaan.nilai_baru,
                              permintaan.alasan[:255])
        s.commit()
        return hasil

    def jalankan_manual(self, s, id_pengguna):
        """Sinkronisasi ulang atas permintaan admin (naskah Subbab 2.1.1).

        Siklus yang gagal tetap di-commit. Kalau jalankan_siklus() sendiri yang
        melempar -- bukan satu selnya -- maka tanpa commit di sini baris
        SIKLUS_SINKRONISASI akan hilang saat koneksi ditutup, dan admin melihat
        dialog "Sinkronisasi gagal" tetapi tab riwayat kosong: kegagalan yang
        tidak meninggalkan jejak justru kegagalan yang paling perlu tercatat.
        """
        try:
            hasil = sp.jalankan_siklus(s, KODE_SEL, simpan=True, pemicu="manual",
                                       id_pengguna=id_pengguna,
                                       cetak=lambda *a: None)
        except Exception:                                   # noqa: BLE001
            try:
                s.commit()
            except Exception:                               # noqa: BLE001
                pass
            raise
        s.commit()
        return hasil


class LayananRiwayat:
    """Layanan riwayat prediksi dan ketelitian model."""
    def __init__(self):
        """Menyiapkan repositori prediksi."""
        self.r = repo.PrediksiRepository()

    def riwayat(self, s, kode_sel, batas, hanya_terisi):
        """Riwayat prediksi untuk versi model produksi, opsional hanya yang sudah punya nilai aktual."""
        return self.r.riwayat(s, kode_sel, batas, hanya_terisi, VERSI_MODEL)

    def ketelitian(self, s):
        """hitungMae dan hitungRmse pada Class Diagram.

        Pengamatan berstatus 'dikecualikan' disaring di tingkat kueri: galat
        terhadap nilai yang sudah dinilai salah admin tidak bermakna.
        """
        k = bd.ketelitian_operasional(s)
        if not k or not k["n"]:
            return {"n": 0}
        hasil = {"n": int(k["n"])}

        # Cakupan: rentang waktu dan jam mana saja yang sudah tersampel. Tanpa
        # ini, angka "n = 90" tidak membedakan 9 jam sore yang berulang dari
        # 9 jam yang tersebar sepanjang hari, padahal keduanya sangat berbeda
        # kekuatannya. Sekaligus membuat angka Bab 4 dapat direproduksi, karena
        # MAE adalah rerata berjalan yang bergeser tiap ada baris baru.
        hasil["jam_awal"] = k["jam_awal"]
        hasil["jam_akhir"] = k["jam_akhir"]
        hasil["jam_berbeda"] = int(k["jam_berbeda"]) if k["jam_berbeda"] else 0
        hasil["jam_tercakup"] = sorted(k["jam_tercakup"] or [])
        hasil["jam_belum_tercakup"] = [j for j in range(24)
                                       if j not in set(hasil["jam_tercakup"])]

        for nama, kunci in (("mae_stacking", "mae_stacking"),
                            ("rmse_stacking", "rmse_stacking"),
                            ("mae_xgboost", "mae_xgboost"),
                            ("rmse_xgboost", "rmse_xgboost"),
                            ("mae_random_forest", "mae_rf"),
                            ("rmse_random_forest", "rmse_rf"),
                            ("mae_persistensi", "mae_persistensi"),
                            ("rmse_persistensi", "rmse_persistensi")):
            hasil[nama] = float(k[kunci]) if k[kunci] is not None else None
        if hasil.get("rmse_persistensi"):
            # Definisi Bab 3: rasio MSE, bukan rasio RMSE.
            hasil["skill_score"] = 1 - (hasil["rmse_stacking"] / hasil["rmse_persistensi"]) ** 2
        return hasil
