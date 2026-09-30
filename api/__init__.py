"""Lapisan web aplikasi prediksi SO2.

Pemetaan terhadap Class Diagram revisi (33 kelas):

  Gambar 4a — Entitas     -> api/skema.py     (model tanggapan Pydantic)
  Gambar 4a — Repositori  -> api/repositori.py (tujuh repositori)
  Gambar 4b — Kendali     -> api/controller.py (enam APIRouter)
  Gambar 4b — Layanan     -> api/layanan.py    (enam layanan)
  Gambar 4b — Pendukung   -> berkas di akar folder, sudah ada sejak Fase 3a/3b:
        PembangunFitur, ModelStacking, KlasifikasiKualitasUdara -> model.py
        OpenMeteoClient                                          -> penarikan.py
        ValidatorPengamatan                                      -> validasi.py
        PenjadwalSinkronisasi                                    -> penjadwal.py

Kelas layanan mengakses basis data hanya lewat repositori, sesuai catatan pada
rancangan Class Diagram.
"""
