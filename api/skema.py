"""Model tanggapan — lapisan Entitas pada Class Diagram (Gambar 4a)."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class Lokasi(BaseModel):
    kode_sel: str
    nama: str
    wilayah_administratif: str
    lintang: float
    bujur: float
    elevasi: float
    karakteristik: Optional[str] = None
    urutan_tampil: int


class Pengamatan(BaseModel):
    id_pengamatan: int
    kode_sel: str
    waktu: datetime
    so2: float
    suhu: float
    kelembapan: float
    titik_embun: float
    curah_hujan: float
    tekanan_permukaan: float
    tutupan_awan: float
    kecepatan_angin: float
    arah_angin: float
    status: str
    alasan_anomali: Optional[str] = None


class TitikRiwayat(BaseModel):
    waktu: datetime
    so2: float
    status: str


class Prediksi(BaseModel):
    id_prediksi: int
    kode_sel: str
    nama_lokasi: str
    waktu_prediksi: datetime
    waktu_dasar: datetime
    nilai_so2: float
    nilai_xgboost: float
    nilai_random_forest: float
    kategori: str
    melampaui_baku_mutu: bool
    rasio_baku_mutu: float
    nilai_aktual: Optional[float] = None
    selisih: Optional[float] = None
    versi_model: str
    dibuat_pada: datetime


class Kemutakhiran(BaseModel):
    """Keterangan kemutakhiran data, dijanjikan naskah Subbab 2.1.1."""
    waktu_data_terakhir: Optional[datetime] = None
    tertinggal_jam: Optional[int] = None
    mutakhir: bool


class PrediksiTerkini(BaseModel):
    prediksi: Optional[Prediksi] = None
    kemutakhiran: Kemutakhiran
    so2_terakhir: Optional[float] = None
    pesan: Optional[str] = None


class StatusSel(BaseModel):
    kode_sel: str
    nama: str
    waktu_data_terakhir: Optional[datetime] = None
    tertinggal_jam: Optional[int] = None
    mutakhir: bool
    jumlah_pengamatan: int
    jumlah_anomali: int
    sinkronisasi_terakhir: Optional[datetime] = None
    status_sinkronisasi: Optional[str] = None
    pesan_galat: Optional[str] = None


class Ketelitian(BaseModel):
    n: int
    mae_stacking: Optional[float] = None
    rmse_stacking: Optional[float] = None
    mae_xgboost: Optional[float] = None
    rmse_xgboost: Optional[float] = None
    mae_random_forest: Optional[float] = None
    rmse_random_forest: Optional[float] = None
    mae_persistensi: Optional[float] = None
    rmse_persistensi: Optional[float] = None
    skill_score: Optional[float] = None
    # Cakupan evaluasi — lihat LayananRiwayat.ketelitian.
    jam_awal: Optional[datetime] = None
    jam_akhir: Optional[datetime] = None
    jam_berbeda: int = 0
    jam_tercakup: list[int] = []
    jam_belum_tercakup: list[int] = []


class PermintaanMasuk(BaseModel):
    username: str
    kata_sandi: str


class Token(BaseModel):
    akses_token: str
    jenis_token: str = "bearer"
    nama_lengkap: str
    peran: str


class PermintaanKoreksi(BaseModel):
    id_pengamatan: int
    tindakan: str                      # tandai_anomali|kecualikan|pulihkan|ubah_nilai
    alasan: str
    kolom_diubah: Optional[str] = None
    nilai_baru: Optional[float] = None


class Koreksi(BaseModel):
    id_koreksi: int
    id_pengamatan: int
    kode_sel: str
    waktu_pengamatan: datetime
    nama_lengkap: str
    tindakan: str
    kolom_diubah: Optional[str] = None
    nilai_lama: Optional[float] = None
    nilai_baru: Optional[float] = None
    alasan: str
    waktu_koreksi: datetime
