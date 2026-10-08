import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { panggil } from '../api.js'

// Pop-up Profil Admin, dibuka dari baris nama pada kaki sidebar.
//
// Hanya menampilkan rincian akun. Rincian datang dari /api/auth/saya — bukan
// dari isi token — supaya yang tampil adalah keadaan terkini di basis data.

// Dialog Profil Admin: menampilkan rincian akun yang sedang masuk.
export default function ProfilAdmin({ pengguna, setPengguna, tutup }) {
  const [profil, setProfil] = useState(pengguna)
  const kotak = useRef(null)

  // Tutup dengan Escape, seperti dialog Sorot.
  useEffect(() => {
    function padaTombol(e) {
      if (e.key === 'Escape') tutup()
    }
    window.addEventListener('keydown', padaTombol)
    return () => window.removeEventListener('keydown', padaTombol)
  }, [tutup])

  // Rincian lengkap belum tentu ada pada objek pengguna yang diwarisi dari
  // halaman Masuk, jadi disegarkan di sini.
  useEffect(() => {
    panggil('/api/auth/saya')
      .then((isi) => { setProfil(isi); setPengguna(isi) })
      .catch(() => {})
  }, [setPengguna])

  // Dirender lewat portal ke <body>: .sisi bersifat sticky sehingga membentuk
  // stacking context sendiri, dan tirai fixed di dalamnya ikut terperangkap di
  // bawah elemen ber-position pada konten utama (mis. grafik Recharts).
  return createPortal(
    <div className="sorot-tirai" onClick={tutup} role="dialog" aria-modal="true"
         aria-label="Profil admin">
      <div className="profil-kotak" ref={kotak} onClick={(e) => e.stopPropagation()}>
        <button className="profil-tutup" onClick={tutup} aria-label="Tutup">×</button>

        <div className="profil-kepala">
          <div className="profil-awalan" aria-hidden="true">
            {(profil?.nama_lengkap || '?').trim().charAt(0).toUpperCase()}
          </div>
          <div>
            <h2>{profil?.nama_lengkap || '—'}</h2>
          </div>
        </div>

        <Rincian profil={profil} />
      </div>
    </div>,
    document.body,
  )
}

// Tampilan rincian akun.
function Rincian({ profil }) {
  return (
    <dl className="profil-rincian">
      <div>
        <dt>Nama lengkap</dt>
        <dd>{profil?.nama_lengkap || '—'}</dd>
      </div>
      <div>
        <dt>Username</dt>
        <dd>{profil?.username || '—'}</dd>
      </div>
      <div>
        <dt>Peran</dt>
        <dd>{profil?.peran || '—'}</dd>
      </div>
      <div>
        <dt>Status akun</dt>
        <dd>{profil?.aktif ? 'Aktif' : 'Nonaktif'}</dd>
      </div>
    </dl>
  )
}
