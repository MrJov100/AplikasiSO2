# Aplikasi Prediksi SO2 — Fase 3a (irisan tegak)

Skripsi Jovandi Todana, 535230027, Teknik Informatika Untar.

Tujuan berkas-berkas di folder ini **bukan** aplikasi lengkap, melainkan
membuktikan satu hal yang belum pernah diuji: bahwa model dapat membaca tiga
pengamatan terakhir **dari PostgreSQL**, menghasilkan prediksi, dan menuliskannya
kembali ke tabel PREDIKSI. Naskah Subbab 2.1 menyebut jalur itu sebagai jalur
utama, sedangkan yang selama ini teruji justru jaring pengamannya (penarikan
langsung ke Open-Meteo).

Setelah irisan ini terbukti, barulah FastAPI dan penjadwal dibangun di atasnya.

(Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned) ; (& "c:\Penyimpanan Utama\Dekstop\C.Database1\AplikasiSO2\.venv\Scripts\Activate.ps1")

## Isi folder

| Berkas                   | Fungsi                                                                                                                                                                            |
| ------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `konfigurasi.py`         | membaca `.env`; konstanta Tabel 2.1; pemetaan nama kolom basis data ke nama fitur model                                                                                           |
| `model.py`               | memuat berkas `.joblib`, menyandikan arah angin, menyusun vektor fitur, menjalankan stacking. Fungsinya disalin apa adanya dari `ModulInferensiFIX.ipynb` supaya angkanya identik |
| `basis_data.py`          | membaca tiga pengamatan terakhir, menulis prediksi dengan kebijakan upsert                                                                                                        |
| `konversi_model.py`      | konversi sekali jalan berkas Colab menjadi berkas portabel                                                                                                                        |
| `uji_koneksi.py`         | pemeriksaan awal: versi pustaka, berkas model, koneksi, hak akses                                                                                                                 |
| `jalankan_prediksi.py`   | program utama                                                                                                                                                                     |
| `uji_bandingkan.py`      | membandingkan jalur basis data dengan jalur Open-Meteo                                                                                                                            |
| `penarikan.py`           | penarikan Open-Meteo dengan percobaan ulang dan jeda menggandakan                                                                                                                 |
| `validasi.py`            | lima lapis validasi, ambang dibaca dari `ambang_anomali.json`                                                                                                                     |
| `segarkan_pengamatan.py` | satu siklus sinkronisasi: tarik, validasi, upsert                                                                                                                                 |
| `isi_nilai_aktual.py`    | isi `nilai_aktual` pada PREDIKSI, laporkan ketelitian operasional                                                                                                                 |
| `penjadwal.py`           | penjadwal per jam yang merangkai ketiga langkah                                                                                                                                   |
| `buat_admin.py`          | membuat akun admin pertama                                                                                                                                                        |
| `api/`                   | lapisan web FastAPI: skema, repositori, layanan, controller                                                                                                                       |

---

## Langkah demi langkah

### 1. Pastikan Python 3.13 terpasang

Buka PowerShell, jalankan:

```powershell
py --list
```

Harus ada `3.13`. Lingkungan pelatihan memakai Python 3.13.15. Kalau belum ada,
unduh dari python.org dan pasang, **centang "Add python.exe to PATH"**.

### 2. Buka folder ini di VS Code

File > Open Folder, pilih:

```
C:\Penyimpanan Utama\Dekstop\C.Database1\AplikasiSO2
```

Lalu buka terminal di dalam VS Code dengan Ctrl+Shift+` (backtick).

### 3. Buat lingkungan virtual

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Kalau PowerShell menolak dengan pesan "running scripts is disabled", jalankan
dulu perintah ini lalu ulangi baris aktivasi:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

Setelah aktif, awal baris terminal akan bertuliskan `(.venv)`.

### 4. Pasang pustaka

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Versinya dikunci persis seperti lingkungan pelatihan. **Jangan dilonggarkan.**
`joblib.load` bisa berhasil dengan versi berbeda tetapi menghasilkan angka yang
berbeda pula — kegagalan diam yang paling berbahaya di seluruh proyek ini.

Catatan: xgboost 3.4.1 menuntut Python 3.12 ke atas, jadi langkah 1 tidak bisa
dilewati dengan Python 3.11.

### 5. Siapkan berkas `.env`

```powershell
copy .env.contoh .env
```

Buka `.env` di VS Code, isi `PG_PASSWORD` dengan kata sandi peran `so2_app` yang
Anda tetapkan saat menjalankan `01_peran_dan_basis_data.sql`. Ada dua folder
model yang harus benar:

- `FOLDER_MODEL_ASLI` — berkas dari Colab, `Gxx_skenario2_model.joblib`
- `FOLDER_MODEL` — berkas portabel, `...\Skenario2\model_portabel`

Berkas `.env` sudah masuk `.gitignore`, jadi kata sandinya tidak ikut ke Git.

### 5b. Konversi model, sekali jalan

```powershell
python konversi_model.py
```

**Mengapa perlu.** Berkas `.joblib` dari Colab tidak dapat dimuat di Windows:
`joblib.load` berhenti dengan `XGBoostError: input stream corrupted`.
Berkasnya tidak rusak — berkas yang sama berhasil dimuat di Linux dengan versi
pustaka yang persis sama dan SHA-256 yang cocok. Penyebabnya buffer pickle
XGBoost yang memang tidak portabel antarsistem operasi.

Booster kesepuluh sel sudah dikonversi lebih dahulu menjadi `Gxx_xgb.ubj` dan
tersedia di folder `model_portabel`. Perintah di atas melengkapinya dengan
`Gxx_bundel.joblib` berisi RandomForest, Ridge, dan metadata — keduanya pickle
scikit-learn biasa yang memang portabel dan sudah terbukti terbaca di Windows.

Konversi ini **sekali jalan**. Sesudahnya tidak ada penonaktifan apa pun di kode
yang berjalan setiap hari.

Keluarannya sepuluh baris berakhiran `OK`, masing-masing bundel sekitar 33–44 MB.

### 6. Pemeriksaan awal

```powershell
python uji_koneksi.py
```

Harus berakhir dengan `SEMUA PEMERIKSAAN LOLOS`, dan melaporkan 363.770 baris
pengamatan dengan yang terbaru `2026-09-27 23:00:00`.

Kalau gagal di langkah 3, penyebab tersering adalah kata sandi salah atau
PostgreSQL belum berjalan. Kalau gagal di langkah 1, versi pustaka tidak cocok —
ulangi langkah 4.

### 7. Prediksi percobaan, tanpa menulis apa pun

```powershell
python jalankan_prediksi.py --sel G04 --sekarang "2026-09-27 23:00"
```

**`--sekarang` wajib untuk saat ini.** Pengamatan terbaru di basis data berhenti
di 27 September 23:00, sedangkan penjaga kemutakhiran menolak data yang
tertinggal lebih dari satu jam dari jam berjalan. Tanpa `--sekarang`, program
akan menolak dengan benar — itu penjaganya bekerja, bukan galat. Setelah
penjadwal Fase 3b berjalan dan basis data selalu mutakhir, parameter ini tidak
diperlukan lagi.

Keluarannya menampilkan jam target, ketiga jam lag beserta `id_pengamatan`-nya,
prediksi XGBoost, Random Forest, dan stacking, serta kategorinya.

### 8. Tulis ke basis data

```powershell
python jalankan_prediksi.py --sel G04 --sekarang "2026-09-27 23:00" --simpan
```

Program akan menulis satu baris ke tabel PREDIKSI lalu membacakan kembali kolom
`kategori`, `rasio_baku_mutu`, dan `melampaui_baku_mutu` yang **dihitung basis
data sendiri** sebagai generated column. Program membandingkannya dengan
hitungan Python; kalau berbeda, akan muncul peringatan.

### 9. Periksa di pgAdmin

```sql
SELECT p.id_prediksi, l.kode_sel, p.waktu_dasar, p.waktu_prediksi,
       p.nilai_xgboost, p.nilai_random_forest, p.nilai_so2,
       p.kategori, p.rasio_baku_mutu, p.melampaui_baku_mutu,
       p.id_pengamatan_t1, p.id_pengamatan_t2, p.id_pengamatan_t3,
       p.versi_model, p.dibuat_pada
FROM   prediksi p JOIN lokasi l ON l.id_lokasi = p.id_lokasi
ORDER  BY p.dibuat_pada DESC;
```

### 10. Uji kesetaraan dengan Open-Meteo

```powershell
python uji_bandingkan.py --sel G04 --target "2026-09-28 00:00"
```

Menghitung vektor fitur dua kali — dari basis data dan dari Open-Meteo — lalu
membandingkan kedelapan belas fiturnya satu per satu. Harus berakhir `LOLOS`.

Ini bukti bahwa seed basis data setia pada sumbernya, dan bahwa jalur utama
menghasilkan angka yang sama dengan jaring pengaman. Perlu koneksi internet.

Catatan: jam targetnya harus masih terjangkau `past_days=3`, jadi jalankan uji
ini dalam tiga hari setelah 28 September. Lewat itu, pilih `--target` yang lebih
dekat ke hari ini — tetapi jam tersebut belum tentu ada di basis data, sehingga
uji ini memang paling bermakna dikerjakan sekarang.

### 11. Kesepuluh sel sekaligus

```powershell
python jalankan_prediksi.py --semua --sekarang "2026-09-27 23:00" --simpan
```

Menguji sepuluh berkas model sekaligus dan mengisi sepuluh baris PREDIKSI.
Jalankan dua kali: jalan kedua harus **memperbarui** baris yang sama, bukan
menambah baris baru — itu membuktikan kekangan `uk_prediksi_lokasi_waktu` dan
kebijakan upsert bekerja, sekaligus menutup persoalan prediksi kembar.

---

### 12. Segarkan tabel PENGAMATAN

```powershell
python segarkan_pengamatan.py                 # coba-coba, tidak menulis
python segarkan_pengamatan.py --simpan
```

Satu siklus sinkronisasi penuh: menarik SO₂ dan delapan variabel meteorologi
untuk kesepuluh sel, menerapkan lima lapis validasi, lalu meng-upsert ke tabel
PENGAMATAN serta mencatat SIKLUS_SINKRONISASI dan SINKRONISASI_LOKASI.

**Mengapa seluruh jendela ditulis ulang, bukan hanya jam terbaru.** Arsip
Open-Meteo masih berubah untuk jam-jam terakhir: nilai yang ditarik sebelum
sebuah run selesai adalah prakiraan, dan diganti analisis kemudian. Pemeriksaan
29 September pada G04 memperlihatkan batasnya jatuh tepat di 19.00 WIB, yaitu
12.00 UTC, batas run 12z. Tanpa upsert seluruh jendela, prakiraan usang akan
menetap selamanya dan dipakai sebagai lag.

**Keputusan admin tidak ditimpa.** Baris berstatus `dikecualikan` hanya pernah
disetel admin; upsert mempertahankan status dan alasannya, tetapi nilai
pengukurannya tetap disegarkan. Status `anomali` dihitung ulang karena itu
keputusan sistem.

Jalankan dua kali: jalan kedua harus melaporkan `sisip 0` dan `perbarui` sebanyak
jumlah barisnya — bukti upsert bekerja.

Sesudah itu ulangi langkah 8 supaya prediksi dibentuk dari data yang segar.

### 13. Isi nilai aktual

```powershell
python isi_nilai_aktual.py                # coba-coba
python isi_nilai_aktual.py --simpan
python isi_nilai_aktual.py --ketelitian   # hanya laporan, tidak mengubah apa pun
```

Sebuah prediksi dibentuk untuk jam yang belum terjadi, sehingga nilai
sebenarnya baru diketahui satu jam kemudian. Modul ini mengisinya. Kolom
`selisih` terisi sendiri karena ia generated column.

Laporan ketelitiannya memuat MAE dan RMSE operasional untuk stacking, XGBoost,
Random Forest, dan baseline persistensi, beserta skill score — bahan langsung
untuk Bab 4. Pengamatan berstatus `dikecualikan` tetap diisi nilai aktualnya
supaya Halaman Riwayat Prediksi menampilkannya, tetapi disaring dari hitungan
ketelitian.

**Jangan membuat prediksi massal ke belakang untuk mengisi tabel ini.** Prediksi
yang dibentuk sekarang atas data yang sudah direvisi menjadi analisis akan
terlihat lebih baik daripada yang sebenarnya dicapai sistem saat berjalan
langsung, dan MAE/RMSE operasionalnya menjadi optimistis.

### 14. Nyalakan penjadwal

```powershell
python penjadwal.py --coba      # satu siklus, tidak menulis
python penjadwal.py --sekali    # satu siklus, menulis
python penjadwal.py             # jalan terus, hentikan dengan Ctrl+C
```

Setiap jam pada menit ke-`MENIT_JADWAL` (bawaan 10), penjadwal menjalankan tiga
langkah berurutan: segarkan pengamatan, bentuk prediksi, isi nilai aktual.
Urutannya mengikat — langkah 2 dan 3 membaca dari tabel yang disegarkan
langkah 1.

Menit keberangkatannya bukan nol dengan sengaja: arsip Open-Meteo perlu waktu
memuat jam yang baru lewat, dan berangkat tepat di menit nol membuat jam
terakhir sering belum tersedia sehingga penjaga kemutakhiran menolak.

Kalau satu jalan belum selesai saat jadwal berikutnya tiba, jalan baru tidak
dimulai dan jadwal yang terlewat digabung menjadi satu, supaya panggilan API
tidak menumpuk.

Biarkan menyala selama mungkin sebelum sidang: catatan operasional di tabel
PREDIKSI hanya bisa terkumpul dengan berjalan, tidak bisa dibuat ke belakang.

### 15. Buat akun admin

```powershell
python buat_admin.py --username admin --nama "Jovandi Todana"
```

Tabel PENGGUNA kosong sampai perintah ini dijalankan, jadi tanpa ini halaman
admin tidak bisa dimasuki. Kata sandi ditanyakan tanpa ditampilkan dan tidak
pernah tercatat; yang disimpan hanya hash bcrypt-nya.

Isi juga `KUNCI_TOKEN` pada `.env` dengan teks acak panjang:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

### 16. Jalankan API

```powershell
uvicorn api.main:app --reload
```

Buka http://localhost:8000/docs — dokumentasi endpoint otomatis, lengkap dengan
tombol coba. Berguna untuk pengujian black box Fase 5 dan untuk mendemonstrasikan
bahwa setiap janji naskah punya endpoint-nya.

Untuk diakses dari komputer lain di jaringan yang sama:

```powershell
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

Saat start, kesepuluh model dimuat sekali ke memori — bukan tiap permintaan.

**Enam controller sesuai Class Diagram:**

| Controller  | Awalan             | Akses  |
| ----------- | ------------------ | ------ |
| Autentikasi | `/api/auth`        | publik |
| Prediksi    | `/api/prediksi`    | publik |
| Visualisasi | `/api/visualisasi` | publik |
| Informasi   | `/api/informasi`   | publik |
| Monitoring  | `/api/monitoring`  | admin  |
| Riwayat     | `/api/riwayat`     | admin  |

### 17. Jalankan antarmuka React

Sembilan halaman sudah lengkap di `antarmuka/`:

| Halaman             | Jalur          | Akses  |
| ------------------- | -------------- | ------ |
| Beranda             | `/`            | publik |
| Prediksi SO₂        | `/prediksi`    | publik |
| Visualisasi Riwayat | `/visualisasi` | publik |
| Informasi Lokasi    | `/lokasi`      | publik |
| FAQ                 | `/faq`         | publik |
| Tentang             | `/tentang`     | publik |
| Masuk               | `/masuk`       | publik |
| Monitoring Data     | `/monitoring`  | admin  |
| Riwayat Prediksi    | `/riwayat`     | admin  |

Saat pengembangan, dua proses berjalan berdampingan:

```powershell
uvicorn api.main:app --reload          # jendela pertama, porta 8000
cd antarmuka; npm install; npm run dev # jendela kedua, porta 5173
```

Buka http://localhost:5173. Permintaan `/api` diteruskan Vite ke porta 8000,
jadi tidak ada persoalan lintas asal.

Untuk demonstrasi dan pengujian black box, cukup satu proses:

```powershell
cd antarmuka; npm run build; cd ..
uvicorn api.main:app
```

FastAPI mendeteksi `antarmuka/dist` dan menyajikannya sendiri, sehingga seluruh
aplikasi berada pada http://localhost:8000 — satu alamat, satu proses.

`npm install` perlu jaringan dan hanya dijalankan sekali. Folder `node_modules`
tidak perlu diserahkan bersama naskah; `package.json` sudah mengikat versinya.

## Yang belum ada di folder ini (milik Fase 4 dan seterusnya)

- Pengujian black box (Fase 5) dan pengujian UEQ, mengacu Gambar 22 benchmark.
- Catatan operasional Bab 4, yang hanya terkumpul dengan membiarkan penjadwal
  menyala.
