import { useEffect, useRef, useState } from 'react'
import { panggil, tanggalPanjang } from '../api.js'

// Pop-up Profil Admin, dibuka dari baris nama pada kaki sidebar.
//
// Tiga bagian dalam satu dialog: rincian akun, ganti nama lengkap, dan ganti
// kata sandi. Rincian datang dari /api/auth/saya — bukan dari isi token —
// supaya nama yang baru diganti langsung tampil benar.

function Medan({ label, petunjuk, ...sisa }) {
  return (
    <label className="medan">
      <span>{label}</span>
      <input {...sisa} />
      {petunjuk && <small className="kecil">{petunjuk}</small>}
    </label>
  )
}

export default function ProfilAdmin({ pengguna, setPengguna, tutup }) {
  const [profil, setProfil] = useState(pengguna)
  const [bagian, setBagian] = useState('rincian')   // rincian|nama|sandi
  const kotak = useRef(null)

  // Tutup dengan Escape, seperti dialog Sorot.
  useEffect(() => {
    function padaTombol(e) {
      if (e.key === 'Escape') tutup()
    }
    window.addEventListener('keydown', padaTombol)
    return () => window.removeEventListener('keydown', padaTombol)
  }, [tutup])

  // Rincian lengkap (termasuk tanggal pembuatan akun) belum tentu ada pada
  // objek pengguna yang diwarisi dari halaman Masuk, jadi disegarkan di sini.
  useEffect(() => {
    panggil('/api/auth/saya')
      .then((isi) => { setProfil(isi); setPengguna(isi) })
      .catch(() => {})
  }, [setPengguna])

  function selesaiNama(baru) {
    setProfil(baru)
    setPengguna(baru)
    setBagian('rincian')
  }

  return (
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
            <p className="kecil">@{profil?.username} · {profil?.peran}</p>
          </div>
        </div>

        {bagian === 'rincian' && (
          <Rincian profil={profil} pilih={setBagian} />
        )}
        {bagian === 'nama' && (
          <GantiNama nama={profil?.nama_lengkap || ''} selesai={selesaiNama}
                     batal={() => setBagian('rincian')} />
        )}
        {bagian === 'sandi' && (
          <GantiKataSandi selesai={() => setBagian('rincian')}
                          batal={() => setBagian('rincian')} />
        )}
      </div>
    </div>
  )
}

function Rincian({ profil, pilih }) {
  return (
    <>
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
        <div>
          <dt>Terakhir masuk</dt>
          <dd>{profil?.terakhir_masuk
            ? new Date(profil.terakhir_masuk).toLocaleString('id-ID')
            : 'Belum pernah'}</dd>
        </div>
        <div>
          <dt>Akun dibuat</dt>
          <dd>{profil?.dibuat_pada ? tanggalPanjang(profil.dibuat_pada) : '—'}</dd>
        </div>
      </dl>

      <div className="profil-aksi">
        <button onClick={() => pilih('nama')}>Ganti nama</button>
        <button onClick={() => pilih('sandi')}>Ganti kata sandi</button>
      </div>
    </>
  )
}

function GantiNama({ nama, selesai, batal }) {
  const [nilai, setNilai] = useState(nama)
  const [galat, setGalat] = useState(null)
  const [sedang, setSedang] = useState(false)

  async function kirim(e) {
    e.preventDefault()
    setGalat(null); setSedang(true)
    try {
      const isi = await panggil('/api/auth/profil', {
        method: 'PATCH',
        body: JSON.stringify({ nama_lengkap: nilai }),
      })
      selesai(isi)
    } catch (e2) {
      setGalat(e2.message)
    } finally {
      setSedang(false)
    }
  }

  const berubah = nilai.trim() !== nama.trim()

  return (
    <form onSubmit={kirim} className="profil-borang">
      <h3>Ganti nama</h3>
      <Medan label="Nama lengkap" value={nilai} autoFocus maxLength={100}
             petunjuk="Tiga sampai seratus karakter."
             onChange={(e) => setNilai(e.target.value)} />

      {galat && <div className="catatan galat">{galat}</div>}

      <div className="profil-aksi">
        <button className="utama" type="submit"
                disabled={sedang || !berubah || nilai.trim().length < 3}>
          {sedang ? 'Menyimpan…' : 'Simpan'}
        </button>
        <button type="button" onClick={batal} disabled={sedang}>Batal</button>
      </div>
    </form>
  )
}

function GantiKataSandi({ selesai, batal }) {
  const [lama, setLama] = useState('')
  const [baru, setBaru] = useState('')
  const [ulang, setUlang] = useState('')
  const [galat, setGalat] = useState(null)
  const [sedang, setSedang] = useState(false)
  const [berhasil, setBerhasil] = useState(false)

  async function kirim(e) {
    e.preventDefault()
    // Kesamaan ulangan diperiksa di sisi ini saja; server tidak perlu tahu
    // ulangannya, cukup kata sandi lama dan baru.
    if (baru !== ulang) { setGalat('Ulangan kata sandi tidak sama.'); return }
    setGalat(null); setSedang(true)
    try {
      await panggil('/api/auth/kata-sandi', {
        method: 'PATCH',
        body: JSON.stringify({ kata_sandi_lama: lama, kata_sandi_baru: baru }),
      })
      setBerhasil(true)
      setLama(''); setBaru(''); setUlang('')
    } catch (e2) {
      setGalat(e2.message)
    } finally {
      setSedang(false)
    }
  }

  if (berhasil) {
    return (
      <div className="profil-borang">
        <div className="catatan info">
          Kata sandi berhasil diganti. Pakai kata sandi baru saat masuk lagi
          nanti; sesi yang sedang berjalan tidak terputus.
        </div>
        <div className="profil-aksi">
          <button className="utama" onClick={selesai} autoFocus>Selesai</button>
        </div>
      </div>
    )
  }

  const lengkap = lama && baru.length >= 8 && ulang

  return (
    <form onSubmit={kirim} className="profil-borang">
      <h3>Ganti kata sandi</h3>
      <Medan label="Kata sandi lama" type="password" value={lama} autoFocus
             autoComplete="current-password"
             onChange={(e) => setLama(e.target.value)} />
      <Medan label="Kata sandi baru" type="password" value={baru}
             autoComplete="new-password" petunjuk="Minimal delapan karakter."
             onChange={(e) => setBaru(e.target.value)} />
      <Medan label="Ulangi kata sandi baru" type="password" value={ulang}
             autoComplete="new-password"
             onChange={(e) => setUlang(e.target.value)} />

      {galat && <div className="catatan galat">{galat}</div>}

      <div className="profil-aksi">
        <button className="utama" type="submit" disabled={sedang || !lengkap}>
          {sedang ? 'Menyimpan…' : 'Simpan'}
        </button>
        <button type="button" onClick={batal} disabled={sedang}>Batal</button>
      </div>
    </form>
  )
}
