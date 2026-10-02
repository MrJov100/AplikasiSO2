// Pembungkus pemanggilan API. Token disimpan di localStorage supaya sesi admin
// bertahan saat halaman disegarkan.
const KUNCI = 'so2_token'

// Membaca, menyimpan, dan menghapus token akses admin di localStorage.
export const ambilToken = () => localStorage.getItem(KUNCI)
export const simpanToken = (t) => localStorage.setItem(KUNCI, t)
export const hapusToken = () => localStorage.removeItem(KUNCI)

// Memanggil endpoint API dengan token (bila ada); menghapus token saat 401 dan
// melempar Error berpesan dari server bila tanggapan gagal.
export async function panggil(jalur, opsi = {}) {
  const kepala = { 'Content-Type': 'application/json', ...(opsi.headers || {}) }
  const token = ambilToken()
  if (token) kepala.Authorization = `Bearer ${token}`

  const tanggapan = await fetch(jalur, { ...opsi, headers: kepala })

  if (tanggapan.status === 401) {
    hapusToken()
    throw new Error('Sesi berakhir atau belum masuk. Silakan masuk kembali.')
  }
  if (!tanggapan.ok) {
    let pesan = `Galat ${tanggapan.status}`
    try { const isi = await tanggapan.json(); pesan = isi.detail || pesan } catch {}
    throw new Error(pesan)
  }
  return tanggapan.json()
}

// ---------- pembantu tampilan ----------
// Pemetaan nama kategori kualitas udara ke kelas CSS-nya.
export const KELAS_KATEGORI = {
  'Baik': 'baik', 'Sedang': 'sedang', 'Buruk': 'buruk', 'Sangat Buruk': 'sangat-buruk',
}

// Memformat waktu menjadi "tgl bln jj.mm" (atau hanya "jj.mm" bila denganTanggal false).
export function jam(waktu, denganTanggal = true) {
  if (!waktu) return '—'
  const d = new Date(waktu)
  const hh = String(d.getHours()).padStart(2, '0')
  const mm = String(d.getMinutes()).padStart(2, '0')
  if (!denganTanggal) return `${hh}.${mm}`
  const tgl = d.toLocaleDateString('id-ID', { day: 'numeric', month: 'short' })
  return `${tgl} ${hh}.${mm}`
}

// Memformat tanggal panjang bahasa Indonesia, mis. "Senin, 5 Mei 2026".
export function tanggalPanjang(waktu) {
  if (!waktu) return '—'
  return new Date(waktu).toLocaleDateString('id-ID',
    { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })
}

// Memformat angka dengan jumlah desimal tertentu; "—" bila kosong.
export const angka = (n, desimal = 2) =>
  (n === null || n === undefined) ? '—' : Number(n).toFixed(desimal)
