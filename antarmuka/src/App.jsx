import { useEffect, useState } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import Sidebar from './komponen/Sidebar.jsx'
import { ambilToken, panggil } from './api.js'

import Beranda from './halaman/Beranda.jsx'
import Prediksi from './halaman/Prediksi.jsx'
import Visualisasi from './halaman/Visualisasi.jsx'
import InformasiLokasi from './halaman/InformasiLokasi.jsx'
import Faq from './halaman/Faq.jsx'
import Tentang from './halaman/Tentang.jsx'
import Masuk from './halaman/Masuk.jsx'
import Monitoring from './halaman/Monitoring.jsx'
import RiwayatPrediksi from './halaman/RiwayatPrediksi.jsx'
import Monev from './halaman/Monev.jsx'

// Komponen akar: memulihkan sesi admin dari token, lalu menyusun sidebar dan rute
// halaman; halaman Monitoring, Riwayat, serta MonEv SO₂ hanya bisa dibuka admin.
export default function App() {
  const [pengguna, setPengguna] = useState(null)
  const [siap, setSiap] = useState(false)

  // Token bisa saja tersisa dari sesi sebelumnya; diperiksa dulu ke server
  // supaya menu admin tidak muncul dengan token yang sudah kedaluwarsa.
  useEffect(() => {
    if (!ambilToken()) { setSiap(true); return }
    panggil('/api/auth/saya')
      .then(setPengguna)
      .catch(() => setPengguna(null))
      .finally(() => setSiap(true))
  }, [])

  if (!siap) return <div className="tengah">Memuat…</div>

  const khususAdmin = (elemen) => (pengguna ? elemen : <Navigate to="/masuk" replace />)

  return (
    <div className="bingkai">
      <Sidebar pengguna={pengguna} setPengguna={setPengguna} />
      <main className="isi">
        <Routes>
          <Route path="/" element={<Beranda admin={!!pengguna} />} />
          <Route path="/prediksi" element={<Prediksi admin={!!pengguna} />} />
          <Route path="/prediksi/:kodeSel" element={<Prediksi admin={!!pengguna} />} />
          <Route path="/visualisasi" element={<Visualisasi admin={!!pengguna} />} />
          <Route path="/visualisasi/:kodeSel" element={<Visualisasi admin={!!pengguna} />} />
          <Route path="/lokasi" element={<InformasiLokasi admin={!!pengguna} />} />
          <Route path="/faq" element={<Faq />} />
          <Route path="/tentang" element={<Tentang />} />
          <Route path="/masuk" element={<Masuk pengguna={pengguna} setPengguna={setPengguna} />} />
          <Route path="/monitoring" element={khususAdmin(<Monitoring />)} />
          <Route path="/riwayat" element={khususAdmin(<RiwayatPrediksi />)} />
          <Route path="/monev" element={khususAdmin(<Monev />)} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
        <footer className="kaki-halaman">© 2026 Selterra - Jovandi Todana</footer>
      </main>
    </div>
  )
}
