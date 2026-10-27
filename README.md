# Aplikasi Prediksi Konsentrasi SO₂ Jabodetabek

Skripsi Jovandi Todana, 535230027, Teknik Informatika Untar.

Aplikasi web yang memprediksi konsentrasi SO₂ satu jam ke depan pada sepuluh sel
grid Jabodetabek. Model stacking (XGBoost + Random Forest + Ridge) membaca tiga
pengamatan terakhir **dari PostgreSQL**, menghasilkan prediksi, dan menuliskannya
ke tabel PREDIKSI. Penarikan langsung ke Open-Meteo hanyalah jaring pengaman.

Alamat produksi: **https://selterra.web.app**

## Daftar isi

1. [Gambaran sistem](#1-gambaran-sistem)
2. [Isi folder](#2-isi-folder)
3. [Pengembangan di komputer lokal](#3-pengembangan-di-komputer-lokal)
4. [Penerapan di Google Cloud](#4-penerapan-di-google-cloud)
   - [4.1 Sumber daya](#41-sumber-daya)
   - [4.2 Memperbarui aplikasi](#42-memperbarui-aplikasi)
   - [4.3 Skrip deploy.ps1](#43-skrip-deployps1)
   - [4.4 Perintah operasional](#44-perintah-operasional)
   - [4.5 Menyiapkan dari nol](#45-menyiapkan-dari-nol)
   - [4.6 Masalah yang pernah muncul](#46-masalah-yang-pernah-muncul)
5. [Yang belum ada](#5-yang-belum-ada)

---

## 1. Gambaran sistem

```
Pengunjung / admin
        │  https://selterra.web.app
        ▼
Firebase Hosting ──── /api/**  ───▶  Cloud Run  so2-api  (FastAPI + 10 model)
 (React, folder dist)                      │
                                           │ IP privat (Direct VPC egress)
                                           ▼
                        Cloud SQL so2-db (PostgreSQL 18)
                                           ▲
Cloud Scheduler ── tiap jam, menit ke-10 ──▶ Cloud Run Job  so2-siklus
                                              (penjadwal.py --sekali)
                                              └─▶ Open-Meteo (internet)
```

| Bagian     | Di komputer lokal          | Di produksi                        |
| ---------- | -------------------------- | ---------------------------------- |
| Antarmuka  | `npm run dev` (porta 5173) | Firebase Hosting, situs `selterra` |
| API        | `uvicorn` (porta 8000)     | Cloud Run service `so2-api`        |
| Penjadwal  | `python penjadwal.py`      | Cloud Run Job + Cloud Scheduler    |
| Basis data | PostgreSQL lokal           | Cloud SQL `so2-db` (IP privat)     |
| Rahasia    | berkas `.env`              | Secret Manager                     |

Frontend memanggil alamat relatif `/api/...`. Firebase Hosting meneruskan semua
permintaan `/api/**` ke Cloud Run, sehingga tidak ada persoalan lintas asal (CORS).

---

## 2. Isi folder

| Berkas                           | Fungsi                                                                                                                                                                            |
| -------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `konfigurasi.py`                 | membaca `.env`; konstanta Tabel 2.1; pemetaan nama kolom basis data ke nama fitur model                                                                                           |
| `model.py`                       | memuat berkas `.joblib`, menyandikan arah angin, menyusun vektor fitur, menjalankan stacking. Fungsinya disalin apa adanya dari `ModulInferensiFIX.ipynb` supaya angkanya identik |
| `basis_data.py`                  | membaca tiga pengamatan terakhir, menulis prediksi dengan kebijakan upsert, mencatat siklus sinkronisasi                                                                          |
| `konversi_model.py`              | konversi sekali jalan berkas Colab menjadi berkas portabel                                                                                                                        |
| `uji_koneksi.py`                 | pemeriksaan awal: versi pustaka, berkas model, koneksi, hak akses                                                                                                                 |
| `jalankan_prediksi.py`           | membentuk prediksi satu atau semua sel                                                                                                                                            |
| `uji_bandingkan.py`              | membandingkan jalur basis data dengan jalur Open-Meteo                                                                                                                            |
| `penarikan.py`                   | penarikan Open-Meteo dengan percobaan ulang dan jeda menggandakan                                                                                                                 |
| `segarkan_pengamatan.py`         | satu siklus sinkronisasi: tarik, upsert                                                                                                                                           |
| `isi_nilai_aktual.py`            | isi `nilai_aktual` pada PREDIKSI, laporkan ketelitian operasional                                                                                                                 |
| `penjadwal.py`                   | penjadwal per jam yang merangkai ketiga langkah                                                                                                                                   |
| `buat_admin.py`                  | membuat akun admin pertama                                                                                                                                                        |
| `migrasi_kolom_langkah.py`       | menambah kolom rincian langkah pada SIKLUS_SINKRONISASI (perlu hak pemilik tabel)                                                                                                 |
| `api/`                           | lapisan web FastAPI: skema, repositori, layanan, controller                                                                                                                       |
| `antarmuka/`                     | antarmuka React (Vite); `firebase.json` dan `.firebaserc` untuk Firebase Hosting                                                                                                  |
| `Dockerfile`                     | citra container untuk Cloud Run (API dan job siklus memakai citra yang sama)                                                                                                      |
| `deploy.ps1`                     | skrip satu perintah untuk men-deploy frontend dan backend                                                                                                                         |
| `.dockerignore`, `.gcloudignore` | berkas yang tidak ikut masuk ke citra dan ke unggahan build                                                                                                                       |
| `model_portabel/`                | **tidak ada di Git.** Salinan 21 berkas model (`Gxx_bundel.joblib`, `Gxx_xgb.ubj`, `metadata_model.json`) yang dimasukkan ke citra Docker                                         |

---

## 3. Pengembangan di komputer lokal

### 3.1 Pastikan Python 3.13 terpasang

```powershell
py --list
```

Harus ada `3.13`. Lingkungan pelatihan memakai Python 3.13.15. Kalau belum ada,
unduh dari python.org dan pasang, **centang "Add python.exe to PATH"**.

### 3.2 Buka folder ini di VS Code

File > Open Folder, pilih `C:\Penyimpanan Utama\Dekstop\AplikasiSO2`,
lalu buka terminal dengan Ctrl+Shift+` (backtick).

### 3.3 Buat lingkungan virtual

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

### 3.4 Pasang pustaka

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Versinya dikunci persis seperti lingkungan pelatihan. **Jangan dilonggarkan.**
`joblib.load` bisa berhasil dengan versi berbeda tetapi menghasilkan angka yang
berbeda pula — kegagalan diam yang paling berbahaya di seluruh proyek ini.

Catatan: xgboost 3.4.1 menuntut Python 3.12 ke atas, jadi langkah 3.1 tidak bisa
dilewati dengan Python 3.11.

### 3.5 Siapkan berkas `.env`

```powershell
copy .env.contoh .env
```

Buka `.env`, isi `PG_PASSWORD` dengan kata sandi peran `so2_app` yang Anda
tetapkan saat menjalankan `01_peran_dan_basis_data.sql`. Pastikan `PG_PORT`
sesuai dengan porta PostgreSQL lokal Anda. Ada dua folder model yang harus benar:

- `FOLDER_MODEL_ASLI` — berkas dari Colab, `Gxx_skenario2_model.joblib`
- `FOLDER_MODEL` — berkas portabel, `...\Skenario2\model_portabel`

Berkas `.env` sudah masuk `.gitignore`, jadi kata sandinya tidak ikut ke Git.
Di produksi, nilai-nilai ini tidak dibaca dari `.env`, melainkan dari variabel
lingkungan Cloud Run dan Secret Manager.

### 3.6 Konversi model, sekali jalan

```powershell
python konversi_model.py
```

**Mengapa perlu.** Berkas `.joblib` dari Colab tidak dapat dimuat di Windows:
`joblib.load` berhenti dengan `XGBoostError: input stream corrupted`. Berkasnya
tidak rusak — berkas yang sama berhasil dimuat di Linux dengan versi pustaka yang
persis sama dan SHA-256 yang cocok. Penyebabnya buffer pickle XGBoost yang memang
tidak portabel antarsistem operasi.

Booster kesepuluh sel sudah dikonversi lebih dahulu menjadi `Gxx_xgb.ubj` dan
tersedia di folder `model_portabel`. Perintah di atas melengkapinya dengan
`Gxx_bundel.joblib` berisi RandomForest, Ridge, dan metadata — keduanya pickle
scikit-learn biasa yang memang portabel dan sudah terbukti terbaca di Windows.

Konversi ini **sekali jalan**. Keluarannya sepuluh baris berakhiran `OK`,
masing-masing bundel sekitar 33–44 MB.

### 3.7 Pemeriksaan awal

```powershell
python uji_koneksi.py
```

Harus berakhir dengan `SEMUA PEMERIKSAAN LOLOS`, dan melaporkan jumlah baris
pengamatan beserta waktu pengamatan terbaru.

Kalau gagal di langkah 3, penyebab tersering adalah kata sandi salah atau
PostgreSQL belum berjalan. Kalau gagal di langkah 1, versi pustaka tidak cocok —
ulangi langkah 3.4.

### 3.8 Prediksi percobaan, tanpa menulis apa pun

```powershell
python jalankan_prediksi.py --sel G04
```

Penjaga kemutakhiran menolak data yang tertinggal lebih dari satu jam dari jam
berjalan. Pada basis data yang tidak lagi diperbarui (misalnya basis data lokal
yang penjadwalnya sudah dimatikan), program akan menolak dengan benar — itu
penjaganya bekerja, bukan galat. Untuk menguji dengan data lama, berikan jam
acuan secara eksplisit:

```powershell
python jalankan_prediksi.py --sel G04 --sekarang "2026-09-27 23:00"
```

Keluarannya menampilkan jam target, ketiga jam lag beserta `id_pengamatan`-nya,
prediksi XGBoost, Random Forest, dan stacking, serta kategorinya.

### 3.9 Tulis ke basis data

```powershell
python jalankan_prediksi.py --sel G04 --simpan
```

Program menulis satu baris ke tabel PREDIKSI lalu membacakan kembali kolom
`kategori`, `rasio_baku_mutu`, dan `melampaui_baku_mutu` yang **dihitung basis
data sendiri** sebagai generated column. Program membandingkannya dengan hitungan
Python; kalau berbeda, akan muncul peringatan.

Periksa hasilnya di pgAdmin:

```sql
SELECT p.id_prediksi, l.kode_sel, p.waktu_dasar, p.waktu_prediksi,
       p.nilai_xgboost, p.nilai_random_forest, p.nilai_so2,
       p.kategori, p.rasio_baku_mutu, p.melampaui_baku_mutu,
       p.id_pengamatan_t1, p.id_pengamatan_t2, p.id_pengamatan_t3,
       p.versi_model, p.dibuat_pada
FROM   prediksi p JOIN lokasi l ON l.id_lokasi = p.id_lokasi
ORDER  BY p.dibuat_pada DESC;
```

### 3.10 Uji kesetaraan dengan Open-Meteo

```powershell
python uji_bandingkan.py --sel G04 --target "2026-09-28 00:00"
```

Menghitung vektor fitur dua kali — dari basis data dan dari Open-Meteo — lalu
membandingkan kedelapan belas fiturnya satu per satu. Harus berakhir `LOLOS`.
Ini bukti bahwa seed basis data setia pada sumbernya, dan bahwa jalur utama
menghasilkan angka yang sama dengan jaring pengaman. Perlu koneksi internet.

Jam targetnya harus masih terjangkau `past_days=3`, jadi ujilah dalam tiga hari
setelah jam yang dipilih.

### 3.11 Kesepuluh sel sekaligus

```powershell
python jalankan_prediksi.py --semua --simpan
```

Menguji sepuluh berkas model sekaligus dan mengisi sepuluh baris PREDIKSI.
Jalankan dua kali: jalan kedua harus **memperbarui** baris yang sama, bukan
menambah baris baru — itu membuktikan kekangan `uk_prediksi_lokasi_waktu` dan
kebijakan upsert bekerja, sekaligus menutup persoalan prediksi kembar.

### 3.12 Segarkan tabel PENGAMATAN

```powershell
python segarkan_pengamatan.py                 # coba-coba, tidak menulis
python segarkan_pengamatan.py --simpan
```

Satu siklus sinkronisasi penuh: menarik SO₂ dan delapan variabel meteorologi
untuk kesepuluh sel, lalu meng-upsert ke tabel PENGAMATAN serta mencatat SIKLUS_SINKRONISASI dan SINKRONISASI_LOKASI.

**Mengapa seluruh jendela ditulis ulang, bukan hanya jam terbaru.** Arsip
Open-Meteo masih berubah untuk jam-jam terakhir: nilai yang ditarik sebelum
sebuah run selesai adalah prakiraan, dan diganti analisis kemudian. Pemeriksaan
29 September pada G04 memperlihatkan batasnya jatuh tepat di 19.00 WIB, yaitu
12.00 UTC, batas run 12z. Tanpa upsert seluruh jendela, prakiraan usang akan
menetap selamanya dan dipakai sebagai lag.

**Data disimpan apa adanya.** Nilai pengamatan disimpan persis seperti yang
dikirim sumber, setelah pra-pemrosesan yang sama dengan saat pelatihan
(pemangkasan SO₂ negatif menjadi nol). Tidak ada penandaan maupun perubahan
nilai oleh sistem atau admin. Nilai yang mustahil secara fisika ditolak
kekangan CHECK pada basis data.

Jalankan dua kali: jalan kedua harus melaporkan `sisip 0` dan `perbarui` sebanyak
jumlah barisnya — bukti upsert bekerja.

### 3.13 Isi nilai aktual

```powershell
python isi_nilai_aktual.py                # coba-coba
python isi_nilai_aktual.py --simpan
python isi_nilai_aktual.py --ketelitian   # hanya laporan, tidak mengubah apa pun
```

Sebuah prediksi dibentuk untuk jam yang belum terjadi, sehingga nilai sebenarnya
baru diketahui satu jam kemudian. Modul ini mengisinya. Kolom `selisih` terisi
sendiri karena ia generated column.

Laporan ketelitiannya memuat MAE dan RMSE operasional untuk stacking, XGBoost,
Random Forest, dan baseline persistensi, beserta skill score — bahan langsung
untuk Bab 4.

**Jangan membuat prediksi massal ke belakang untuk mengisi tabel ini.** Prediksi
yang dibentuk sekarang atas data yang sudah direvisi menjadi analisis akan
terlihat lebih baik daripada yang sebenarnya dicapai sistem saat berjalan
langsung, dan MAE/RMSE operasionalnya menjadi optimistis.

### 3.14 Penjadwal

```powershell
python penjadwal.py --coba      # satu siklus, tidak menulis
python penjadwal.py --sekali    # satu siklus, menulis
python penjadwal.py             # jalan terus, hentikan dengan Ctrl+C
```

Setiap jam pada menit ke-`MENIT_JADWAL` (bawaan 10), penjadwal menjalankan tiga
langkah berurutan: segarkan pengamatan, bentuk prediksi, isi nilai aktual.
Urutannya mengikat — langkah 2 dan 3 membaca dari tabel yang disegarkan langkah 1.

Menit keberangkatannya bukan nol dengan sengaja: arsip Open-Meteo perlu waktu
memuat jam yang baru lewat, dan berangkat tepat di menit nol membuat jam terakhir
sering belum tersedia sehingga penjaga kemutakhiran menolak.

Kalau satu jalan belum selesai saat jadwal berikutnya tiba, jalan baru tidak
dimulai dan jadwal yang terlewat digabung menjadi satu, supaya panggilan API tidak
menumpuk.

**Penjadwal lokal hanya untuk pengembangan.** Di produksi, siklus per jam
dijalankan Cloud Scheduler (lihat [4.1](#41-sumber-daya)). Catatan operasional di
tabel PREDIKSI hanya bisa terkumpul dengan berjalan, tidak bisa dibuat ke
belakang, jadi pastikan jadwal produksi tetap menyala sampai sidang.

### 3.15 Buat akun admin

```powershell
python buat_admin.py --username admin --nama "Jovandi Todana"
```

Tabel PENGGUNA kosong sampai perintah ini dijalankan, jadi tanpa ini halaman admin
tidak bisa dimasuki. Kata sandi ditanyakan tanpa ditampilkan dan tidak pernah
tercatat; yang disimpan hanya hash bcrypt-nya.

Isi juga `KUNCI_TOKEN` pada `.env` dengan teks acak panjang:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

### 3.16 Jalankan API

```powershell
uvicorn api.main:app --reload
```

Buka http://localhost:8000/docs — dokumentasi endpoint otomatis, lengkap dengan
tombol coba. Berguna untuk pengujian black box dan untuk mendemonstrasikan bahwa
setiap janji naskah punya endpoint-nya.

Untuk diakses dari komputer lain di jaringan yang sama:

```powershell
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

Saat start, kesepuluh model dimuat sekali ke memori — bukan tiap permintaan.

**Enam controller:**

| Controller  | Awalan             | Akses  |
| ----------- | ------------------ | ------ |
| Autentikasi | `/api/auth`        | publik |
| Prediksi    | `/api/prediksi`    | publik |
| Visualisasi | `/api/visualisasi` | publik |
| Informasi   | `/api/informasi`   | publik |
| Monitoring  | `/api/monitoring`  | admin  |
| Riwayat     | `/api/riwayat`     | admin  |

### 3.17 Jalankan antarmuka React

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

Buka http://localhost:5173. Permintaan `/api` diteruskan Vite ke porta 8000, jadi
tidak ada persoalan lintas asal. API lokal ini membaca basis data **lokal**.

Untuk melihat tampilan baru dengan data produksi tanpa menjalankan API lokal,
ubah sementara `target` proxy di `antarmuka/vite.config.js` ke alamat Cloud Run
(`https://so2-api-532707674958.asia-southeast2.run.app`), lalu **kembalikan ke
`http://127.0.0.1:8000`** sesudahnya. Ingat bahwa cara ini terhubung ke basis data
produksi: jangan memicu sinkronisasi manual saat mencobanya.

Untuk demonstrasi lokal dengan satu proses:

```powershell
cd antarmuka; npm run build; cd ..
uvicorn api.main:app
```

FastAPI mendeteksi `antarmuka/dist` dan menyajikannya sendiri, sehingga seluruh
aplikasi berada pada http://localhost:8000.

`npm install` perlu jaringan dan hanya dijalankan sekali. Folder `node_modules`
tidak perlu diserahkan bersama naskah; `package.json` sudah mengikat versinya.

---

## 4. Penerapan di Google Cloud

### 4.1 Sumber daya

| Sumber daya       | Nama / nilai                                                                                                     |
| ----------------- | ---------------------------------------------------------------------------------------------------------------- |
| Project           | `so2-jabodetabek-510408` (di organisasi `jovanditodana-org`)                                                     |
| Region            | `asia-southeast2` (Jakarta)                                                                                      |
| Cloud SQL         | instance `so2-db`, PostgreSQL 18, IP privat `10.4.240.3`, basis data `so2_jabodetabek`, peran aplikasi `so2_app` |
| Cloud Run service | `so2-api`, 4 GiB, 2 CPU, `min-instances 0`, akses publik                                                         |
| Cloud Run Job     | `so2-siklus`, menjalankan `python penjadwal.py --sekali`, 4 GiB, 2 CPU, batas 900 detik                          |
| Cloud Scheduler   | `so2-siklus-per-jam`, jadwal `10 * * * *`, zona `Asia/Jakarta`                                                   |
| Secret Manager    | `so2-pg-password` (kata sandi `so2_app`), `so2-kunci-token` (kunci JWT)                                          |
| Artifact Registry | `cloud-run-source-deploy` (citra hasil build)                                                                    |
| Firebase Hosting  | situs `selterra` → https://selterra.web.app                                                                      |
| Akun layanan      | `532707674958-compute@developer.gserviceaccount.com` (service, job, build, scheduler)                            |

Variabel lingkungan service dan job: `PG_HOST=10.4.240.3`, `PG_PORT=5432`,
`PG_DB=so2_jabodetabek`, `PG_USER=so2_app`, `VERSI_MODEL`. Service juga memakai
`MASA_TOKEN_JAM`. Kata sandi dan kunci token datang dari Secret Manager, tidak
pernah ditulis di konfigurasi.

Situs Firebase bawaan (`so2-jabodetabek-510408.web.app`) tidak bisa dihapus dan
tetap menayangkan versi terakhir yang dideploy sebelum situs `selterra` dibuat.

### 4.2 Memperbarui aplikasi

Deploy mengambil kode dari **folder di komputer Anda**, bukan dari GitHub. Kode
tidak tersinkron otomatis: setiap bagian harus di-deploy sendiri.

| Yang Anda ubah                                              | Yang dijalankan                               |
| ----------------------------------------------------------- | --------------------------------------------- |
| Tampilan (`antarmuka/`)                                     | `.\deploy.ps1 -Frontend`                      |
| Kode API (`api/`, `konfigurasi.py`, dst.)                   | `.\deploy.ps1 -Backend`                       |
| Kode siklus per jam (`penjadwal.py`, `basis_data.py`, dst.) | `.\deploy.ps1 -Backend` (job ikut diperbarui) |
| Frontend dan backend sekaligus                              | `.\deploy.ps1`                                |
| Struktur basis data                                         | SQL di Cloud SQL Studio, lalu deploy kode     |
| Variabel lingkungan atau kata sandi                         | lihat langkah 5 di bawah                      |
| Berkas model                                                | lihat langkah 6 di bawah                      |

#### Memperbarui frontend

1. Ubah kode di `antarmuka/src/`.
2. Periksa di lokal. Jalankan API dan antarmuka seperti di [3.17](#317-jalankan-antarmuka-react).
3. Commit perubahan ke Git (disarankan).
4. Publikasikan:

   ```powershell
   cd "C:\Penyimpanan Utama\Dekstop\AplikasiSO2"
   .\deploy.ps1 -Frontend
   ```

   Skrip ini menjalankan `npm run build` lalu `firebase deploy --only hosting`.
   Prosesnya sekitar satu menit dan berakhir dengan `Deploy complete!`.

5. Buka https://selterra.web.app lalu tekan **Ctrl+F5** supaya browser tidak
   memakai versi lama dari cache.

Perubahan tampilan **tidak** memerlukan deploy backend atau perubahan basis data.

#### Memperbarui backend

1. Ubah kode Python.
2. Jika perubahan menyentuh struktur tabel atau kolom, terapkan SQL-nya **lebih
   dulu** di Cloud SQL Studio sebagai `postgres` (lihat langkah 4). Kalau terbalik,
   kode baru bisa gagal karena kolom belum ada.
3. Uji di lokal (`uvicorn api.main:app --reload`), lalu commit.
4. Publikasikan:

   ```powershell
   .\deploy.ps1 -Backend
   ```

   Skrip membangun citra baru (5–10 menit), men-deploy `so2-api`, memperbarui
   Cloud Run Job ke citra yang sama, lalu memanggil `/api/sehat` sebagai
   pemeriksaan. Memori, VPC, variabel lingkungan, dan secret dari revisi
   sebelumnya tetap terbawa. Revisi baru baru menerima trafik setelah sehat;
   kalau gagal start, versi lama tetap melayani.

   **Mengapa job ikut diperbarui.** Cloud Run Job menyimpan citra tetap saat
   dibuat dan tidak berubah sendiri. Tanpa langkah ini, penjadwal per jam tetap
   menjalankan kode lama. Gunakan `-TanpaJob` bila yang berubah hanya endpoint API.

#### Langkah 4: mengubah struktur basis data

Perubahan skema tidak ikut deploy kode. Terapkan di **Cloud SQL Studio** (Console

> SQL > `so2-db` > Cloud SQL Studio), login sebagai `postgres` pada basis data
> `so2_jabodetabek`. Peran `so2_app` sengaja tidak punya hak DDL. Tabel baru yang
> dibuat `postgres` otomatis memberi hak data ke `so2_app` lewat
> `ALTER DEFAULT PRIVILEGES`. Simpan perintah SQL-nya sebagai berkas di folder SQL
> supaya riwayatnya terdokumentasi.

#### Langkah 5: mengubah variabel lingkungan atau kata sandi

```powershell
# variabel lingkungan
gcloud run services update so2-api --region asia-southeast2 --update-env-vars "MASA_TOKEN_JAM=24"
gcloud run jobs update so2-siklus --region asia-southeast2 --update-env-vars "VERSI_MODEL=..."

# kata sandi atau kunci: tambah versi baru di Secret Manager (berkas tanpa baris baru)
gcloud secrets versions add so2-pg-password --data-file=berkas-kata-sandi.txt
gcloud run services update so2-api --region asia-southeast2 --update-labels deploy=ulang
```

Baris terakhir memaksa pembuatan revisi baru agar versi rahasia terbaru terbaca.
Hapus berkas kata sandi sementara itu sesudahnya.

#### Langkah 6: mengubah berkas model

Salin berkas model baru ke `model_portabel/`, samakan `VERSI_MODEL` di service dan
job, lalu jalankan `.\deploy.ps1 -Backend`.

#### Kebiasaan yang disarankan

Commit ke Git **sebelum** deploy, supaya yang berjalan di cloud selalu dapat
ditelusuri ke satu commit dan versi lama bisa dipulihkan. Git tidak diperlukan
agar deploy berjalan, tetapi `deploy.ps1` akan memperingatkan bila ada perubahan
yang belum di-commit. Folder `model_portabel/` dan berkas `.env` tidak ikut ke Git.

### 4.3 Skrip deploy.ps1

Dijalankan dari folder proyek utama (`AplikasiSO2`), bukan dari `antarmuka`.

```powershell
.\deploy.ps1                       # frontend + backend + Cloud Run Job
.\deploy.ps1 -Frontend             # hanya frontend (Firebase Hosting)
.\deploy.ps1 -Backend              # backend + Cloud Run Job
.\deploy.ps1 -Backend -TanpaJob    # backend saja, job tidak diperbarui
```

Kalau PowerShell menolak dengan pesan "running scripts is disabled":

```powershell
powershell -ExecutionPolicy Bypass -File .\deploy.ps1 -Frontend
```

Skrip berhenti di langkah pertama yang gagal. Galat `401` dari Firebase berarti
login kedaluwarsa: jalankan `firebase logout` lalu `firebase login`.

Perubahan struktur basis data **tidak** dikerjakan skrip ini.

### 4.4 Perintah operasional

```powershell
# status layanan dan job
gcloud run services describe so2-api --region asia-southeast2
gcloud run jobs executions list --job so2-siklus --region asia-southeast2 --limit 5

# log API
gcloud run services logs read so2-api --region asia-southeast2 --limit 50

# jalankan satu siklus sekarang tanpa menunggu jadwal
gcloud run jobs execute so2-siklus --region asia-southeast2 --wait
gcloud scheduler jobs run so2-siklus-per-jam --location asia-southeast2

# pemeriksaan kesehatan
curl.exe https://selterra.web.app/api/sehat
```

Memeriksa hasil siklus di Cloud SQL Studio:

```sql
SELECT id_siklus, waktu_mulai, status, jumlah_berhasil, prediksi_berhasil,
       prediksi_gagal, aktual_terisi
FROM siklus_sinkronisasi ORDER BY id_siklus DESC LIMIT 5;
```

Siklus yang sehat berstatus `berhasil` dengan 10 penarikan dan 10 prediksi.

**Menghemat biaya saat aplikasi tidak dipakai.** Menghentikan instance Cloud SQL
membuat penjadwal per jam gagal dan menghentikan pengumpulan catatan operasional,
jadi jangan dilakukan selama pengumpulan data berlangsung.

```powershell
gcloud sql instances patch so2-db --activation-policy=NEVER    # hentikan
gcloud sql instances patch so2-db --activation-policy=ALWAYS   # nyalakan
```

Pasang juga _budget alert_ di Console > Billing > Budgets & alerts.

### 4.5 Menyiapkan dari nol

Ringkasan urutan jika seluruh lingkungan harus dibangun ulang (project baru atau
instance dihapus). Semua perintah memakai project `so2-jabodetabek-510408`; ganti
bila berbeda.

1. **Project dan billing.** Pastikan project tertaut ke akun billing aktif
   (`gcloud billing projects describe <project>` harus `billingEnabled: true`) dan
   `gcloud config set project <project>` menunjuk ke project yang benar. Perhatikan
   bahwa **ID project bisa berbeda dari nama tampilannya**.
2. **API.**

   ```powershell
   gcloud services enable sqladmin.googleapis.com compute.googleapis.com servicenetworking.googleapis.com storage.googleapis.com run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com cloudscheduler.googleapis.com
   ```

3. **Cloud SQL.** Buat instance di Console: PostgreSQL 18, Enterprise, preset
   Sandbox, region `asia-southeast2`, single zone, SSD 10 GB, **hanya Private IP**
   (Private Service Access, jaringan `default`; Public IP dilarang kebijakan
   organisasi). Nama instance tidak bisa dipakai ulang selama kurang lebih satu
   minggu setelah dihapus.
4. **Basis data dan peran.**

   ```powershell
   gcloud sql databases create so2_jabodetabek --instance=so2-db --charset=UTF8
   ```

   Lalu di Cloud SQL Studio (login `postgres`). Buat peran lewat SQL, jangan lewat
   tab _Users_: pengguna dari Console otomatis menjadi `cloudsqlsuperuser`.

   ```sql
   CREATE ROLE so2_app WITH LOGIN PASSWORD '<kata-sandi-kuat>'
       NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT CONNECTION LIMIT 20;
   ALTER DATABASE so2_jabodetabek SET timezone = 'Asia/Jakarta';
   REVOKE ALL ON DATABASE so2_jabodetabek FROM PUBLIC;
   GRANT CONNECT ON DATABASE so2_jabodetabek TO so2_app;
   ```

5. **Memindahkan data dari basis data lokal.** Auth Proxy tidak bisa menjangkau IP
   privat dari laptop, jadi gunakan Cloud Storage. Hentikan penjadwal lokal dulu.

   ```powershell
   $env:Path += ";C:\Program Files\PostgreSQL\18\bin"
   $env:PGPASSWORD = "<kata-sandi-so2_app-lokal>"
   pg_dump -h localhost -p 5432 -U so2_app -d so2_jabodetabek --format=plain --no-owner --no-acl -f C:\gcp\so2.sql

   # buang baris \restrict yang tidak dikenal impor Cloud SQL (pg_dump 18)
   $u = New-Object System.Text.UTF8Encoding($false)
   $b = [IO.File]::ReadAllLines("C:\gcp\so2.sql", $u) | Where-Object { $_ -notmatch '^\\(un)?restrict\b' }
   [IO.File]::WriteAllLines("C:\gcp\so2_bersih.sql", $b, $u)

   $B = "so2-impor-510408"
   gcloud storage buckets create gs://$B --location=asia-southeast2 --uniform-bucket-level-access
   gcloud storage cp C:\gcp\so2_bersih.sql gs://$B/
   $sa = gcloud sql instances describe so2-db --format="value(serviceAccountEmailAddress)"
   gcloud storage buckets add-iam-policy-binding gs://$B --member="serviceAccount:$sa" --role="roles/storage.objectViewer"
   gcloud sql import sql so2-db gs://$B/so2_bersih.sql --database=so2_jabodetabek --user=postgres
   ```

   Hak akses dibuang oleh `--no-acl`, jadi pasang ulang di Cloud SQL Studio
   (login `postgres`, basis data `so2_jabodetabek`):

   ```sql
   GRANT USAGE ON SCHEMA public TO so2_app;
   GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO so2_app;
   GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO so2_app;
   ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO so2_app;
   ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO so2_app;
   ```

   Verifikasi: bandingkan jumlah baris tujuh tabel dengan basis data lokal, dan
   pastikan `SHOW timezone` menghasilkan `Asia/Jakarta`. Berkas dump berisi seluruh
   data dan hash kata sandi admin; simpan hanya di komputer sendiri, jangan di-commit,
   dan hapus dari bucket setelah selesai.

6. **Rahasia.** Tulis nilai ke berkas tanpa baris baru, buat secret, lalu beri
   izin ke akun layanan. Kunci token sebaiknya baru, bukan yang di `.env` lokal.

   ```powershell
   $NUM = gcloud projects describe so2-jabodetabek-510408 --format="value(projectNumber)"
   $SA = "$NUM-compute@developer.gserviceaccount.com"
   gcloud secrets create so2-pg-password --data-file=<berkas-kata-sandi>
   gcloud secrets create so2-kunci-token --data-file=<berkas-kunci>
   gcloud secrets add-iam-policy-binding so2-pg-password --member="serviceAccount:$SA" --role="roles/secretmanager.secretAccessor"
   gcloud secrets add-iam-policy-binding so2-kunci-token --member="serviceAccount:$SA" --role="roles/secretmanager.secretAccessor"
   ```

7. **Izin build.** Di project baru, akun layanan build perlu diberi izin:

   ```powershell
   foreach ($r in "roles/cloudbuild.builds.builder","roles/storage.objectViewer","roles/artifactregistry.writer","roles/logging.logWriter") {
     gcloud projects add-iam-policy-binding so2-jabodetabek-510408 --member="serviceAccount:$SA" --role=$r
   }
   ```

8. **Berkas yang dibutuhkan citra.** Salin model ke dalam proyek (dibaca
   `Dockerfile`):

   ```powershell
   mkdir model_portabel
   Copy-Item "<folder>\Skenario2\model_portabel\*" .\model_portabel\
   ```

9. **Cloud Run service.** Memori 2 GiB **tidak cukup** untuk memuat kesepuluh model
   (terbunuh karena memori habis); gunakan 4 GiB dan 2 CPU.

   ```powershell
   gcloud run deploy so2-api --source . --region asia-southeast2 --allow-unauthenticated `
     --memory 4Gi --cpu 2 --cpu-boost --timeout 300 --min-instances 0 --max-instances 3 `
     --network default --subnet default --vpc-egress private-ranges-only `
     --set-env-vars "PG_HOST=10.4.240.3,PG_PORT=5432,PG_DB=so2_jabodetabek,PG_USER=so2_app,VERSI_MODEL=stacking-s2-20260731,MASA_TOKEN_JAM=12" `
     --set-secrets "PG_PASSWORD=so2-pg-password:latest,KUNCI_TOKEN=so2-kunci-token:latest"
   ```

   Ganti `PG_HOST` dengan IP privat instance yang baru bila berbeda. Jika
   `--allow-unauthenticated` ditolak dengan pesan _"do not belong to a permitted
   customer"_, longgarkan kebijakan `iam.allowedPolicyMemberDomains` pada project
   (lihat [4.6](#46-masalah-yang-pernah-muncul)), lalu jalankan:

   ```powershell
   gcloud run services add-iam-policy-binding so2-api --region asia-southeast2 --member="allUsers" --role="roles/run.invoker"
   ```

10. **Cloud Run Job dan Scheduler.**

    ```powershell
    $IMG = gcloud run services describe so2-api --region asia-southeast2 --format="value(spec.template.spec.containers[0].image)"
    gcloud run jobs create so2-siklus --image $IMG --region asia-southeast2 `
      --command python --args "penjadwal.py,--sekali" `
      --memory 4Gi --cpu 2 --task-timeout 900 --max-retries 0 `
      --network default --subnet default --vpc-egress private-ranges-only `
      --set-env-vars "PG_HOST=10.4.240.3,PG_PORT=5432,PG_DB=so2_jabodetabek,PG_USER=so2_app,VERSI_MODEL=stacking-s2-20260731" `
      --set-secrets "PG_PASSWORD=so2-pg-password:latest"

    gcloud run jobs add-iam-policy-binding so2-siklus --region asia-southeast2 --member="serviceAccount:$SA" --role="roles/run.invoker"
    gcloud scheduler jobs create http so2-siklus-per-jam --location asia-southeast2 `
      --schedule "10 * * * *" --time-zone "Asia/Jakarta" `
      --uri "https://run.googleapis.com/v2/projects/so2-jabodetabek-510408/locations/asia-southeast2/jobs/so2-siklus:run" `
      --http-method POST --oauth-service-account-email $SA
    ```

    Uji dengan `gcloud run jobs execute so2-siklus --region asia-southeast2 --wait`
    lalu periksa tabel `siklus_sinkronisasi`.

11. **Firebase Hosting.**

    ```powershell
    firebase login
    firebase projects:addfirebase so2-jabodetabek-510408
    firebase hosting:sites:create selterra --project so2-jabodetabek-510408
    .\deploy.ps1 -Frontend
    ```

    `antarmuka/firebase.json` sudah berisi `"site": "selterra"` serta aturan
    _rewrite_ `/api/**` ke `so2-api` di `asia-southeast2`. ID situs tidak bisa
    diubah setelah dibuat dan harus unik di seluruh dunia.

### 4.6 Masalah yang pernah muncul

| Gejala                                                                 | Penyebab dan penanganan                                                                                                                                                                         |
| ---------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Instance Cloud SQL berstatus `SUSPENDED`, perubahan ditolak 409        | `gcloud` menunjuk ke project yang salah (ID berbeda dari nama tampilan) dan project itu tidak punya billing. Cek `gcloud billing projects describe <project>`                                   |
| Pembuatan instance: "Restrict Public IP access"                        | Kebijakan organisasi melarang Public IP. Gunakan Private IP (Private Service Access)                                                                                                            |
| `pg_dump` 18 menghasilkan impor yang gagal                             | Baris `\restrict` / `\unrestrict` tidak dikenal impor Cloud SQL. Buang seperti di [4.5](#45-menyiapkan-dari-nol) langkah 5                                                                      |
| Studio terkesan login sebagai `so2_app` tetapi `CREATE TABLE` berhasil | Sesi Studio masih berjalan sebagai `postgres`. Cek `SELECT current_user;`. Hak `so2_app` dapat diperiksa dengan `has_schema_privilege('so2_app','public','CREATE')`                             |
| Build gagal: `storage.objects.get` ditolak                             | Akun layanan build belum punya izin. Beri peran seperti di [4.5](#45-menyiapkan-dari-nol) langkah 7                                                                                             |
| Kontainer gagal start, log: `Memory limit of 2048 MiB exceeded`        | Pemuatan sepuluh model butuh lebih dari 2 GiB. Naikkan: `gcloud run services update so2-api --region asia-southeast2 --memory 4Gi --cpu 2`                                                      |
| `allUsers` ditolak: "do not belong to a permitted customer"            | Kebijakan `iam.allowedPolicyMemberDomains` aktif. Admin organisasi dapat menggantinya di tingkat project (Organization Policies, atau `gcloud org-policies set-policy` dengan `allowAll: true`) |
| `firebase` membalas 401 saat `addfirebase` atau `deploy`               | Login Firebase kedaluwarsa. `firebase logout` lalu `firebase login`                                                                                                                             |
| 504 pada situs, tetapi URL Cloud Run langsung berfungsi                | Firebase membatasi permintaan yang diteruskan sekitar 60 detik; _cold start_ (pemuatan model) bisa melewatinya. `gcloud run services update so2-api --region asia-southeast2 --min-instances 1` |
| Perubahan tampilan belum terlihat setelah deploy                       | Cache browser. Tekan Ctrl+F5                                                                                                                                                                    |
| Penjadwal per jam tetap memakai kode lama                              | Cloud Run Job belum diperbarui. Jalankan `.\deploy.ps1 -Backend` (tanpa `-TanpaJob`)                                                                                                            |

---

## 5. Yang belum ada

- Pengujian black box dan pengujian UEQ, mengacu Gambar 22 benchmark.
- Catatan operasional Bab 4, yang hanya terkumpul dengan membiarkan penjadwal
  produksi menyala terus.
