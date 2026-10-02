import { useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { panggil, simpanToken } from '../api.js'

// Halaman Masuk. Permintaan login tidak lewat panggil() karena pembungkus itu
// menerjemahkan setiap 401 menjadi "sesi berakhir"; pada halaman ini 401 justru
// berarti username atau kata sandi salah, dan pesannya harus begitu.
export default function Masuk({ pengguna, setPengguna }) {
  const navigasi = useNavigate()
  const [username, setUsername] = useState('')
  const [kataSandi, setKataSandi] = useState('')
  const [galat, setGalat] = useState(null)
  const [sedang, setSedang] = useState(false)

  if (pengguna) return <Navigate to="/monitoring" replace />

  // Mengirim kredensial ke server; bila sah, menyimpan token dan membuka Monitoring.
  async function kirim(e) {
    e.preventDefault()
    setGalat(null); setSedang(true)
    try {
      const tanggapan = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, kata_sandi: kataSandi }),
      })
      const isi = await tanggapan.json().catch(() => ({}))
      if (!tanggapan.ok) throw new Error(isi.detail || `Galat ${tanggapan.status}`)

      simpanToken(isi.akses_token)
      const saya = await panggil('/api/auth/saya')
      setPengguna(saya)
      navigasi('/monitoring', { replace: true })
    } catch (e2) {
      setGalat(e2.message)
    } finally {
      setSedang(false)
    }
  }

  return (
    <>
      <div className="kepala">
        <h1>Masuk</h1>
        <p>Halaman Monitoring Data dan Riwayat Prediksi hanya untuk admin.</p>
      </div>

      <div className="kartu" style={{ maxWidth: 380 }}>
        <form onSubmit={kirim}>
          <label className="medan">
            <span>Username</span>
            <input value={username} autoFocus autoComplete="username"
                   onChange={(e) => setUsername(e.target.value)} />
          </label>
          <label className="medan">
            <span>Kata sandi</span>
            <input type="password" value={kataSandi} autoComplete="current-password"
                   onChange={(e) => setKataSandi(e.target.value)} />
          </label>

          {galat && <div className="catatan galat" style={{ marginBottom: '.75rem' }}>{galat}</div>}

          <button className="utama" type="submit"
                  disabled={sedang || !username || !kataSandi}>
            {sedang ? 'Memeriksa…' : 'Masuk'}
          </button>
        </form>

        <p className="kecil" style={{ marginTop: '1rem', marginBottom: 0 }}>
          Akun dibuat lewat <code>python buat_admin.py</code>. Tabel pengguna
          kosong sampai perintah itu dijalankan.
        </p>
      </div>
    </>
  )
}
