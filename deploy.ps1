<#
Deploy aplikasi SO2 ke Google Cloud dan Firebase.

    .\deploy.ps1                  frontend + backend + Cloud Run Job
    .\deploy.ps1 -Frontend        hanya frontend (Firebase Hosting)
    .\deploy.ps1 -Backend         hanya backend (Cloud Run service + Cloud Run Job)
    .\deploy.ps1 -Backend -TanpaJob   backend saja, Cloud Run Job tidak diperbarui

Cloud Run Job menyimpan image tetap saat dibuat, jadi ia HARUS diperbarui setiap
kali kode backend yang dipakai siklus per jam berubah. Skrip ini melakukannya
otomatis kecuali -TanpaJob diberikan.

Perubahan struktur database TIDAK ikut. Terapkan lebih dulu lewat Cloud SQL
Studio sebagai postgres, baru jalankan skrip ini.
#>
param(
    [switch]$Frontend,
    [switch]$Backend,
    [switch]$TanpaJob
)

$Proyek  = "so2-jabodetabek-510408"
$Wilayah = "asia-southeast2"
$Layanan = "so2-api"
$NamaJob = "so2-siklus"
$Akar    = $PSScriptRoot

# Tanpa pilihan apa pun, kerjakan frontend dan backend.
if (-not $Frontend -and -not $Backend) { $Frontend = $true; $Backend = $true }

function Gagal($pesan) {
    Write-Host "GAGAL: $pesan" -ForegroundColor Red
    exit 1
}

function Tahap($pesan) {
    Write-Host ""
    Write-Host "=== $pesan ===" -ForegroundColor Cyan
}

# --- Pemeriksaan awal --------------------------------------------------------
Tahap "Pemeriksaan awal"

$aktif = (gcloud config get-value project 2>$null)
if ($aktif -ne $Proyek) {
    Write-Host "Project gcloud aktif '$aktif', diganti ke '$Proyek'."
    gcloud config set project $Proyek | Out-Null
    if ($LASTEXITCODE -ne 0) { Gagal "tidak dapat mengganti project gcloud." }
}

$belumDisimpan = git -C $Akar status --porcelain 2>$null
if ($belumDisimpan) {
    Write-Host "Perhatian: ada perubahan yang belum di-commit ke Git:" -ForegroundColor Yellow
    $belumDisimpan | Select-Object -First 10 | ForEach-Object { Write-Host "  $_" }
    Write-Host "Yang berjalan di cloud nanti tidak persis sama dengan commit terakhir." -ForegroundColor Yellow
}

# --- Frontend ----------------------------------------------------------------
if ($Frontend) {
    Tahap "Frontend: build React lalu deploy ke Firebase Hosting"
    Push-Location (Join-Path $Akar "antarmuka")
    try {
        npm run build
        if ($LASTEXITCODE -ne 0) { Gagal "npm run build." }

        firebase deploy --only hosting
        if ($LASTEXITCODE -ne 0) { Gagal "firebase deploy. Jika galatnya 401, jalankan 'firebase login' ulang." }
    }
    finally { Pop-Location }
}

# --- Backend -----------------------------------------------------------------
if ($Backend) {
    Tahap "Backend: bangun image dan deploy ke Cloud Run ($Layanan)"
    Push-Location $Akar
    try {
        if (-not (Test-Path ".\model_portabel") -or -not (Test-Path ".\data\ambang_anomali.json")) {
            Gagal "folder model_portabel atau data\ambang_anomali.json tidak ada. Salin dulu sesuai panduan."
        }

        # Pengaturan lain (memori, VPC, variabel, secret) tetap dari revisi sebelumnya.
        gcloud run deploy $Layanan --source . --region $Wilayah
        if ($LASTEXITCODE -ne 0) { Gagal "gcloud run deploy." }

        if (-not $TanpaJob) {
            Tahap "Memperbarui Cloud Run Job ($NamaJob) ke image yang sama"
            $citra = gcloud run services describe $Layanan --region $Wilayah `
                --format="value(spec.template.spec.containers[0].image)"
            if (-not $citra) { Gagal "tidak dapat membaca image service." }

            gcloud run jobs update $NamaJob --region $Wilayah --image $citra
            if ($LASTEXITCODE -ne 0) { Gagal "gcloud run jobs update." }
        }
    }
    finally { Pop-Location }

    Tahap "Pemeriksaan kesehatan"
    $alamat = gcloud run services describe $Layanan --region $Wilayah --format="value(status.url)"
    Write-Host "Memanggil $alamat/api/sehat (permintaan pertama bisa 30-60 detik) ..."
    curl.exe -s --max-time 120 "$alamat/api/sehat"
    Write-Host ""
}

Write-Host ""
Write-Host "Selesai." -ForegroundColor Green
if ($Frontend) { Write-Host "Situs: https://selterra.web.app" }
