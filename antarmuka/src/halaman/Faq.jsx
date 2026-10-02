import { useEffect, useState } from 'react'
import { panggil } from '../api.js'
import { Memuat, Galat } from '../komponen/Umum.jsx'

// Halaman FAQ: daftar tanya-jawab dari /api/informasi/faq. Satu butir dapat
// dibuka-tutup supaya halaman tetap ringkas saat butirnya bertambah.
export default function Faq() {
  const [data, setData] = useState(null)
  const [galat, setGalat] = useState(null)
  const [terbuka, setTerbuka] = useState(0)

  useEffect(() => {
    panggil('/api/informasi/faq').then(setData).catch((e) => setGalat(e.message))
  }, [])

  if (galat) return <Galat pesan={galat} />
  if (!data) return <Memuat />

  return (
    <>
      <div className="kepala">
        <h1>Pertanyaan yang Sering Diajukan</h1>
        <p>Keterangan singkat tentang data, cakupan, dan batas pemakaian aplikasi.</p>
      </div>

      {data.map((b, i) => (
        <div key={b.tanya} className="kartu" style={{ marginBottom: '.7rem' }}>
          <button
            onClick={() => setTerbuka(terbuka === i ? -1 : i)}
            style={{
              background: 'none', border: 0, padding: 0, textAlign: 'left',
              width: '100%', font: 'inherit', fontWeight: 600, cursor: 'pointer',
            }}>
            <span style={{
              display: 'inline-block', width: '1em', textAlign: 'center',
              transition: 'transform .3s ease',
              transform: terbuka === i ? 'rotate(180deg)' : 'none',
            }}>{terbuka === i ? '−' : '+'}</span> &nbsp;{b.tanya}
          </button>
          {/* Tinggi dianimasikan lewat grid 0fr -> 1fr agar tak perlu mengukur isi. */}
          <div style={{
            display: 'grid',
            gridTemplateRows: terbuka === i ? '1fr' : '0fr',
            opacity: terbuka === i ? 1 : 0,
            transition: 'grid-template-rows .3s ease, opacity .3s ease',
          }}>
            <div style={{ overflow: 'hidden' }}>
              <p style={{ margin: '.6rem 0 0', color: 'var(--abu)' }}>{b.jawab}</p>
            </div>
          </div>
        </div>
      ))}
    </>
  )
}
