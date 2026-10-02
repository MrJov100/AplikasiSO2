import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { panggil, angka } from '../api.js'
import { Memuat, Galat } from '../komponen/Umum.jsx'

// Halaman Informasi Lokasi: daftar kesepuluh sel grid beserta koordinat,
// elevasi, dan karakteristiknya. Karakteristik itulah alasan kesepuluh sel
// dipilih — perairan, pesisir, industri, urban padat, dataran tinggi.
export default function InformasiLokasi({ admin }) {
  const [data, setData] = useState(null)
  const [galat, setGalat] = useState(null)
  const navigasi = useNavigate()

  useEffect(() => {
    panggil('/api/informasi/lokasi').then(setData).catch((e) => setGalat(e.message))
  }, [])

  if (galat) return <Galat pesan={galat} />
  if (!data) return <Memuat />

  return (
    <>
      <div className="kepala">
        <h1>Informasi Lokasi</h1>
        <p>
          Sepuluh sel grid Jabodetabek yang dipakai penelitian. Tiap sel memiliki
          model tersendiri, dilatih hanya dengan data sel itu.
        </p>
      </div>

      <div className="kartu">
        <table>
          <thead>
            <tr>
              {admin && <th>Kode</th>}
              <th>Nama</th>
              <th>Wilayah administratif</th>
              <th className="angka">Lintang</th>
              <th className="angka">Bujur</th>
              <th className="angka">Elevasi (m)</th>
              <th>Karakteristik</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {data.map((l) => (
              <tr key={l.kode_sel}>
                {admin && <td><b>{l.kode_sel}</b></td>}
                <td>{l.nama}</td>
                <td>{l.wilayah_administratif}</td>
                <td className="angka">{angka(l.lintang, 4)}</td>
                <td className="angka">{angka(l.bujur, 4)}</td>
                <td className="angka">{angka(l.elevasi, 0)}</td>
                <td className="kecil">{l.karakteristik || '—'}</td>
                <td>
                  <button className="kecil"
                          onClick={() => navigasi(`/prediksi/${l.kode_sel}`)}>
                    Prediksi
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}
