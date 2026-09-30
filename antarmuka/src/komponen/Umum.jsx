import { KELAS_KATEGORI } from '../api.js'

export function Lencana({ kategori }) {
  if (!kategori) return <span className="lencana abu">Belum ada</span>
  return <span className={`lencana ${KELAS_KATEGORI[kategori] || 'abu'}`}>{kategori}</span>
}

export function Memuat({ pesan = 'Memuat data…' }) {
  return <div className="tengah">{pesan}</div>
}

export function Galat({ pesan }) {
  return <div className="catatan galat">{pesan}</div>
}

export function Kosong({ pesan }) {
  return <div className="tengah">{pesan}</div>
}

// Daftar tombol halaman ringkas: selalu tampil halaman pertama, terakhir, dan
// tetangga halaman aktif; sisanya diganti elipsis. Contoh (aktif=6 dari 12):
// 1 … 5 6 7 … 12
function itemHalaman(aktif, total, tetangga = 1, batas = 1) {
  const rentang = (a, b) => Array.from({ length: b - a + 1 }, (_, i) => a + i)
  const awal = rentang(1, Math.min(batas, total))
  const akhir = rentang(Math.max(total - batas + 1, batas + 1), total)
  const mulaiTengah = Math.max(
    Math.min(aktif - tetangga, total - batas - tetangga * 2 - 1), batas + 2)
  const akhirTengah = Math.min(
    Math.max(aktif + tetangga, batas + tetangga * 2 + 2), akhir.length ? akhir[0] - 2 : total - 1)
  return [
    ...awal,
    ...(mulaiTengah > batas + 2 ? ['…awal'] : batas + 1 < total - batas ? [batas + 1] : []),
    ...rentang(mulaiTengah, akhirTengah),
    ...(akhirTengah < total - batas - 1 ? ['…akhir'] : total - batas > batas ? [total - batas] : []),
    ...akhir,
  ]
}

/** Navigasi halaman untuk tabel: ‹ 1 2 3 4 5 … 12 › */
export function Halaman({ aktif, total, onUbah }) {
  if (total <= 1) return null
  return (
    <nav className="halaman" aria-label="Navigasi halaman">
      <button disabled={aktif === 1} aria-label="Halaman sebelumnya"
              onClick={() => onUbah(aktif - 1)}>‹</button>
      {itemHalaman(aktif, total).map((n) =>
        typeof n === 'string' ? (
          <span key={n} className="elipsis">…</span>
        ) : (
          <button key={n} className={n === aktif ? 'aktif' : ''}
                  aria-label={`Halaman ${n}`}
                  aria-current={n === aktif ? 'page' : undefined}
                  onClick={() => onUbah(n)}>{n}</button>
        ))}
      <button disabled={aktif === total} aria-label="Halaman berikutnya"
              onClick={() => onUbah(aktif + 1)}>›</button>
    </nav>
  )
}

/** Keterangan kemutakhiran data — dijanjikan naskah Subbab 2.1.1. */
export function Kemutakhiran({ data }) {
  if (!data) return null
  if (data.mutakhir) {
    return (
      <div className="catatan info">
        Data mutakhir. Pengamatan terakhir pukul{' '}
        <b>{new Date(data.waktu_data_terakhir).toLocaleString('id-ID')}</b>.
      </div>
    )
  }
  return (
    <div className="catatan ingat">
      Data belum mutakhir — tertinggal <b>{data.tertinggal_jam} jam</b> dari jam
      berjalan. Pengamatan terakhir pukul{' '}
      <b>{data.waktu_data_terakhir
        ? new Date(data.waktu_data_terakhir).toLocaleString('id-ID')
        : 'tidak diketahui'}</b>.
      Sistem menahan diri daripada menampilkan prediksi untuk jam yang sudah lewat.
    </div>
  )
}
