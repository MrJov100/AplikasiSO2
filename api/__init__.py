"""Lapisan web aplikasi prediksi SO2.

Susunan berlapis:

  Entitas     -> api/skema.py     (model tanggapan Pydantic)
  Repositori  -> api/repositori.py (tujuh repositori)
  Kendali     -> api/controller.py (enam APIRouter)
  Layanan     -> api/layanan.py    (enam layanan)
  Pendukung   -> berkas di akar folder:
        model.py        pembangunan fitur, model stacking, kategori kualitas udara
        penarikan.py    klien Open-Meteo
        penjadwal.py    penjadwal sinkronisasi

Layanan mengakses basis data hanya lewat repositori.
"""
