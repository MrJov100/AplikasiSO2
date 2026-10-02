import { useEffect, useState } from 'react'
import { panggil, angka, jam } from '../api.js'
import { Lencana, Memuat, Galat, Halaman } from '../komponen/Umum.jsx'

// Halaman Riwayat Prediksi (admin). Menampilkan prediksi yang pernah dibentuk
// beserta nilai sebenarnya yang menyusul, dan ketelitian operasionalnya.
// Ringkas daftar jam menjadi rentang: [0,1,2,5,6] -> "00-02, 05-06".
// Daftar 24 angka mentah sulit dibaca sekilas, sedangkan yang perlu terlihat
// adalah ada-tidaknya lubang, bukan tiap angkanya.
function rentangJam(daftar) {
  if (!daftar || !daftar.length) return '—'
  const dua = (n) => String(n).padStart(2, '0')
  const bagian = []
  let awal = daftar[0], akhir = daftar[0]
  for (const j of daftar.slice(1)) {
    if (j === akhir + 1) { akhir = j; continue }
    bagian.push(awal === akhir ? dua(awal) : `${dua(awal)}-${dua(akhir)}`)
    awal = akhir = j
  }
  bagian.push(awal === akhir ? dua(awal) : `${dua(awal)}-${dua(akhir)}`)
  return bagian.join(', ')
}

// Jumlah baris tabel per halaman.
const PER_HALAMAN = 10

// Komponen halaman Riwayat Prediksi: tabel prediksi vs nilai sebenarnya dan
// panel ketelitian operasional model.
export default function RiwayatPrediksi() {
  const [lokasi, setLokasi] = useState([])
  const [sel, setSel] = useState('')
  const [hanyaTerisi, setHanyaTerisi] = useState(false)
  const [baris, setBaris] = useState(null)
  const [telisik, setTelisik] = useState(null)
  const [galat, setGalat] = useState(null)
  const [halaman, setHalaman] = useState(1)

  useEffect(() => { panggil('/api/informasi/lokasi').then(setLokasi).catch(() => {}) }, [])

  useEffect(() => {
    panggil('/api/riwayat/ketelitian').then(setTelisik).catch((e) => setGalat(e.message))
  }, [])

  useEffect(() => {
    setBaris(null)
    setHalaman(1)
    const q = new URLSearchParams({ batas: '300', hanya_terisi: String(hanyaTerisi) })
    if (sel) q.set('kode_sel', sel)
    panggil(`/api/riwayat/prediksi?${q}`).then(setBaris).catch((e) => setGalat(e.message))
  }, [sel, hanyaTerisi])

  return (
    <>
      <div className="kepala">
        <h1>Riwayat Prediksi</h1>
        <p>
          Prediksi yang pernah dibentuk beserta nilai sebenarnya yang menyusul
          satu jam kemudian.
        </p>
      </div>

      {galat && <Galat pesan={galat} />}

      {telisik && (
        <div className="kartu">
          <h3>Ketelitian operasional</h3>
          {telisik.n === 0 ? (
            <p className="kecil">
              Belum ada prediksi yang nilai sebenarnya sudah terisi. Angka ini
              baru muncul setelah penjadwal berjalan beberapa jam.
            </p>
          ) : (
            <>
              <p className="kecil">
                Dihitung dari {telisik.n} prediksi pada{' '}
                <b>{telisik.jam_berbeda} jam berbeda</b>, rentang{' '}
                {jam(telisik.jam_awal)} – {jam(telisik.jam_akhir)}. Prediksi
                dari versi model uji dan jam berstatus <i>dikecualikan</i> tidak
                diikutkan.
              </p>
              <table>
                <thead>
                  <tr><th>Model</th><th className="angka">MAE</th><th className="angka">RMSE</th></tr>
                </thead>
                <tbody>
                  <tr><td><b>Stacking (ditampilkan aplikasi)</b></td>
                      <td className="angka"><b>{angka(telisik.mae_stacking)}</b></td>
                      <td className="angka"><b>{angka(telisik.rmse_stacking)}</b></td></tr>
                  <tr><td>XGBoost</td>
                      <td className="angka">{angka(telisik.mae_xgboost)}</td>
                      <td className="angka">{angka(telisik.rmse_xgboost)}</td></tr>
                  <tr><td>Random Forest</td>
                      <td className="angka">{angka(telisik.mae_random_forest)}</td>
                      <td className="angka">{angka(telisik.rmse_random_forest)}</td></tr>
                  <tr><td>Baseline persistensi</td>
                      <td className="angka">{angka(telisik.mae_persistensi)}</td>
                      <td className="angka">{angka(telisik.rmse_persistensi)}</td></tr>
                </tbody>
              </table>
              {telisik.skill_score !== null && telisik.skill_score !== undefined && (
                <p className="kecil" style={{ marginTop: '.6rem' }}>
                  Skill score terhadap persistensi:{' '}
                  <b>{angka(telisik.skill_score, 3)}</b>
                  {telisik.skill_score <= 0 &&
                    ' — pada rentang ini stacking belum melampaui persistensi.'}
                </p>
              )}
              <p className="kecil" style={{ marginTop: '.4rem' }}>
                Jam tercakup: <b>{rentangJam(telisik.jam_tercakup)}</b>
                {telisik.jam_belum_tercakup?.length > 0 && (
                  <>
                    {' '}· belum tercakup:{' '}
                    <b style={{ color: 'var(--buruk)' }}>
                      {rentangJam(telisik.jam_belum_tercakup)}
                    </b>
                  </>
                )}
              </p>

              <div className="catatan ingat" style={{ marginTop: '.75rem' }}>
                Angka ini <b>tidak sama</b> dengan ketelitian blok uji Bab 4 dan
                biasanya lebih buruk. Saat berjalan, lag t−1 sering masih berupa
                prakiraan yang belum menjadi analisis. Karena itu pula prediksi
                tidak boleh dibentuk ke belakang secara massal: hasilnya akan
                tampak lebih baik daripada capaian sistem yang sebenarnya.
              </div>
            </>
          )}
        </div>
      )}

      <div className="baris-kendali">
        <select value={sel} onChange={(e) => setSel(e.target.value)}>
          <option value="">Semua sel</option>
          {lokasi.map((l) => (
            <option key={l.kode_sel} value={l.kode_sel}>{l.kode_sel} — {l.nama}</option>
          ))}
        </select>
        <label className="kecil" style={{ display: 'flex', alignItems: 'center', gap: '.35rem' }}>
          <input type="checkbox" checked={hanyaTerisi} style={{ width: 'auto' }}
                 onChange={(e) => setHanyaTerisi(e.target.checked)} />
          Hanya yang nilai sebenarnya sudah terisi
        </label>
      </div>

      {!baris && !galat && <Memuat />}

      {baris && (() => {
        const totalHalaman = Math.max(1, Math.ceil(baris.length / PER_HALAMAN))
        const aktif = Math.min(halaman, totalHalaman)
        const mulai = (aktif - 1) * PER_HALAMAN
        const tampil = baris.slice(mulai, mulai + PER_HALAMAN)
        return (
        <div className="kartu">
          <h3>Tabel Daftar Prediksi</h3>
          <p className="kecil">
            {baris.length} baris
            {baris.length > 0 && ` · menampilkan ${mulai + 1}–${mulai + tampil.length}`}
          </p>
          <table>
            <thead>
              <tr>
                <th>No</th>
                <th>Untuk jam</th><th>Sel</th>
                <th className="angka">Stacking</th>
                <th className="angka">XGB</th>
                <th className="angka">RF</th>
                <th className="angka">Sebenarnya</th>
                <th className="angka">Selisih</th>
                <th>Kategori</th>
                <th>Dibentuk</th>
              </tr>
            </thead>
            <tbody>
              {tampil.map((p, i) => (
                // Baris yang tidak ikut dihitung diredupkan, BUKAN disembunyikan
                // apalagi dihapus. Menghapus catatan yang hasilnya buruk demi
                // kerapian adalah hal yang paling sulit dipertanggungjawabkan
                // saat sidang; yang benar adalah menjelaskan mengapa sebuah
                // baris dikecualikan, dan membiarkannya tetap terlihat.
                <tr key={p.id_prediksi}
                    style={p.sebab_tidak_dihitung
                      ? { opacity: .55, background: 'var(--redup, #fafafa)' }
                      : undefined}>
                  <td>{mulai + i + 1}</td>
                  <td>{jam(p.waktu_prediksi)}</td>
                  <td>{p.kode_sel}</td>
                  <td className="angka">{angka(p.nilai_so2)}</td>
                  <td className="angka">{angka(p.nilai_xgboost)}</td>
                  <td className="angka">{angka(p.nilai_random_forest)}</td>
                  <td className="angka">{angka(p.nilai_aktual)}</td>
                  <td className="angka">
                    {p.selisih === null || p.selisih === undefined ? '—' : (
                      <span style={{ color: Math.abs(p.selisih) > 10 ? 'var(--buruk)' : 'inherit' }}>
                        {p.selisih > 0 ? '+' : ''}{angka(p.selisih)}
                      </span>
                    )}
                  </td>
                  <td><Lencana kategori={p.kategori} /></td>
                  <td className="kecil">
                    {jam(p.dibuat_pada)}
                    {p.sebab_tidak_dihitung && (
                      <div style={{ opacity: .85, fontStyle: 'italic' }}>
                        tidak dihitung — {p.sebab_tidak_dihitung}
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <Halaman aktif={aktif} total={totalHalaman} onUbah={setHalaman} />
          <p className="kecil" style={{ marginTop: '.6rem' }}>
            Selisih dihitung sebagai nilai sebenarnya dikurangi prediksi stacking.
            Tanda positif berarti sistem memperkirakan terlalu rendah.
          </p>
          <p className="kecil">
            Baris yang diredupkan tetap disimpan tetapi tidak masuk hitungan
            ketelitian di atas. <i>Versi uji</i> menandai prediksi yang dibentuk
            dengan versi model percobaan, termasuk prediksi yang dibentuk ke
            belakang saat pengembangan — angkanya tidak mewakili capaian sistem
            saat berjalan.
          </p>
        </div>
        )
      })()}
    </>
  )
}
