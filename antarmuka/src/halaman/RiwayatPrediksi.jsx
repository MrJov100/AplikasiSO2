import { useEffect, useState } from "react";
import { panggil, angka, jam } from "../api.js";
import { Lencana, Memuat, Galat, Halaman } from "../komponen/Umum.jsx";

// Halaman Riwayat Prediksi (admin). Menampilkan prediksi yang pernah dibentuk
// beserta nilai sebenarnya yang menyusul, dan ketelitian operasionalnya.

// Jumlah baris tabel per halaman. Baris diminta ke server per halaman
// (paginasi sisi server), sehingga hanya halaman yang dibuka yang dimuat.
const PER_HALAMAN = 10;

// Komponen halaman Riwayat Prediksi: tabel prediksi vs nilai sebenarnya dan
// panel ketelitian operasional model.
export default function RiwayatPrediksi() {
  const [lokasi, setLokasi] = useState([]);
  const [sel, setSel] = useState("");
  // { total, baris } untuk halaman aktif; null selama halaman itu dimuat.
  const [daftar, setDaftar] = useState(null);
  const [memuat, setMemuat] = useState(true);
  const [telisik, setTelisik] = useState(null);
  const [galat, setGalat] = useState(null);
  const [halaman, setHalaman] = useState(1);
  const [info, setInfo] = useState(false);
  const namaSel = Object.fromEntries(lokasi.map((l) => [l.kode_sel, l.nama]));

  useEffect(() => {
    panggil("/api/informasi/lokasi")
      .then(setLokasi)
      .catch(() => {});
  }, []);

  useEffect(() => {
    panggil("/api/riwayat/ketelitian")
      .then(setTelisik)
      .catch((e) => setGalat(e.message));
  }, []);

  // Satu permintaan per halaman yang dibuka. Tanggapan yang tiba sesudah
  // penyaring atau halaman berganti diabaikan, agar baris halaman lama tidak
  // menimpa halaman yang sedang dilihat.
  useEffect(() => {
    let batal = false;
    // Data lama dipertahankan selama memuat agar tinggi halaman tidak runtuh
    // dan posisi gulir tidak melompat ke atas; hanya tabel yang diredupkan.
    setMemuat(true);
    const q = new URLSearchParams({
      halaman: String(halaman),
      per_halaman: String(PER_HALAMAN),
    });
    if (sel) q.set("kode_sel", sel);
    panggil(`/api/riwayat/prediksi?${q}`)
      .then((d) => {
        if (!batal) {
          setDaftar(d);
          setMemuat(false);
        }
      })
      .catch((e) => {
        if (!batal) {
          setGalat(e.message);
          setMemuat(false);
        }
      });
    return () => {
      batal = true;
    };
  }, [sel, halaman]);

  // Mengganti penyaring selalu kembali ke halaman pertama.
  function ubahSel(nilai) {
    setSel(nilai);
    setHalaman(1);
  }

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
                Dihitung dari {telisik.n} prediksi pada{" "}
                <b>{telisik.jam_berbeda} jam berbeda</b>, rentang{" "}
                {jam(telisik.jam_awal)} – {jam(telisik.jam_akhir)}.
              </p>
              <table>
                <thead>
                  <tr>
                    <th>Model</th>
                    <th className="angka">MAE</th>
                    <th className="angka">RMSE</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>
                      <b>Stacking (ditampilkan aplikasi)</b>
                    </td>
                    <td className="angka">
                      <b>{angka(telisik.mae_stacking)}</b>
                    </td>
                    <td className="angka">
                      <b>{angka(telisik.rmse_stacking)}</b>
                    </td>
                  </tr>
                  <tr>
                    <td>XGBoost</td>
                    <td className="angka">{angka(telisik.mae_xgboost)}</td>
                    <td className="angka">{angka(telisik.rmse_xgboost)}</td>
                  </tr>
                  <tr>
                    <td>Random Forest</td>
                    <td className="angka">
                      {angka(telisik.mae_random_forest)}
                    </td>
                    <td className="angka">
                      {angka(telisik.rmse_random_forest)}
                    </td>
                  </tr>
                  <tr>
                    <td>Baseline persistensi</td>
                    <td className="angka">{angka(telisik.mae_persistensi)}</td>
                    <td className="angka">{angka(telisik.rmse_persistensi)}</td>
                  </tr>
                </tbody>
              </table>
              {telisik.skill_score !== null &&
                telisik.skill_score !== undefined && (
                  <p className="kecil" style={{ marginTop: ".6rem" }}>
                    Skill score terhadap persistensi:{" "}
                    <b>{angka(telisik.skill_score, 3)}</b>
                    {telisik.skill_score <= 0 &&
                      " — pada rentang ini stacking belum melampaui persistensi."}
                    <span
                      className="info-ikon"
                      onMouseEnter={() => setInfo(true)}
                      onMouseLeave={() => setInfo(false)}
                    >
                      <span
                        className="tombol"
                        tabIndex={0}
                        role="button"
                        aria-label="Penjelasan skill score"
                        aria-expanded={info}
                        onClick={() => setInfo((v) => !v)}
                        onFocus={() => setInfo(true)}
                        onBlur={() => setInfo(false)}
                      >
                        i
                      </span>
                      {info && (
                        <span className="balon" role="tooltip">
                          Skill score = 1 − (RMSE stacking ÷ RMSE persistensi)².
                          Persistensi = nilai jam depan ditebak sama dengan jam
                          ini. Di atas 0: stacking lebih akurat; 1: sempurna; 0
                          atau negatif: tidak lebih baik.
                        </span>
                      )}
                    </span>
                  </p>
                )}
            </>
          )}
        </div>
      )}

      <div className="baris-kendali">
        <select value={sel} onChange={(e) => ubahSel(e.target.value)}>
          <option value="">Semua sel</option>
          {lokasi.map((l) => (
            <option key={l.kode_sel} value={l.kode_sel}>
              {l.kode_sel} — {l.nama}
            </option>
          ))}
        </select>
      </div>

      {!daftar && !galat && <Memuat />}

      {daftar &&
        (() => {
          const totalHalaman = Math.max(
            1,
            Math.ceil(daftar.total / PER_HALAMAN),
          );
          const aktif = Math.min(halaman, totalHalaman);
          const mulai = (aktif - 1) * PER_HALAMAN;
          const tampil = daftar.baris;
          return (
            <div className="kartu">
              <h3>Tabel Daftar Prediksi</h3>
              <p className="kecil">{daftar.total} baris</p>
              <div
                aria-busy={memuat}
                style={{
                  opacity: memuat ? 0.5 : 1,
                  pointerEvents: memuat ? "none" : undefined,
                  transition: "opacity .15s",
                }}
              >
              <table>
                <thead>
                  <tr>
                    <th>No</th>
                    <th>Untuk jam</th>
                    <th>Nama</th>
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
                    // baris tidak dihitung, dan membiarkannya tetap terlihat.
                    <tr
                      key={p.id_prediksi}
                      style={
                        p.sebab_tidak_dihitung
                          ? {
                              opacity: 0.55,
                              background: "var(--redup, #fafafa)",
                            }
                          : undefined
                      }
                    >
                      <td>{mulai + i + 1}</td>
                      <td>{jam(p.waktu_prediksi)}</td>
                      <td>{namaSel[p.kode_sel] ?? p.kode_sel}</td>
                      <td className="angka">{angka(p.nilai_so2)}</td>
                      <td className="angka">{angka(p.nilai_xgboost)}</td>
                      <td className="angka">{angka(p.nilai_random_forest)}</td>
                      <td className="angka">{angka(p.nilai_aktual)}</td>
                      <td className="angka">
                        {p.selisih === null || p.selisih === undefined ? (
                          "—"
                        ) : (
                          <span
                            style={{
                              color:
                                Math.abs(p.selisih) > 10
                                  ? "var(--buruk)"
                                  : "inherit",
                            }}
                          >
                            {p.selisih > 0 ? "+" : ""}
                            {angka(p.selisih)}
                          </span>
                        )}
                      </td>
                      <td>
                        <Lencana kategori={p.kategori} />
                      </td>
                      <td className="kecil">
                        {jam(p.dibuat_pada)}
                        {p.sebab_tidak_dihitung && (
                          <div style={{ opacity: 0.85, fontStyle: "italic" }}>
                            tidak dihitung — {p.sebab_tidak_dihitung}
                          </div>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              </div>
              <Halaman aktif={aktif} total={totalHalaman} onUbah={setHalaman} />
              <p className="kecil" style={{ marginTop: ".6rem" }}>
                Selisih dihitung sebagai nilai sebenarnya dikurangi prediksi
                stacking. Tanda positif berarti sistem memperkirakan terlalu
                rendah.
              </p>
            </div>
          );
        })()}
    </>
  );
}
