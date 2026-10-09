import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { panggil, angka, jam, tanggalPanjang } from "../api.js";
import { Lencana, Memuat, Galat, Kemutakhiran } from "../komponen/Umum.jsx";

// Halaman Prediksi SO₂: prediksi satu jam ke depan untuk sel yang dipilih,
// beserta keluaran tiap model dan keterangan kemutakhiran data.
export default function Prediksi({ admin }) {
  const { kodeSel } = useParams();
  const navigasi = useNavigate();
  const [lokasi, setLokasi] = useState([]);
  const [dipilih, setDipilih] = useState(kodeSel || "G04");
  const [data, setData] = useState(null);
  const [galat, setGalat] = useState(null);

  useEffect(() => {
    panggil("/api/informasi/lokasi")
      .then(setLokasi)
      .catch(() => {});
  }, []);

  useEffect(() => {
    setData(null);
    setGalat(null);
    panggil(`/api/prediksi/terkini/${dipilih}`)
      .then(setData)
      .catch((e) => setGalat(e.message));
  }, [dipilih]);

  // Mengganti sel yang dipilih dan menyelaraskan alamat halaman.
  function pilih(kode) {
    setDipilih(kode);
    navigasi(`/prediksi/${kode}`, { replace: true });
  }

  const info = lokasi.find((l) => l.kode_sel === dipilih);
  const p = data?.prediksi;
  // Kode pada alamat (mis. /prediksi/G99) tidak ada dalam daftar sel. Daftar
  // yang gagal dimuat (kosong) tidak dianggap bukti bahwa kodenya salah.
  const tidakDikenal = lokasi.length > 0 && !info;

  return (
    <>
      <div className="kepala">
        <h1>Prediksi SO₂</h1>
        <p>Pilih sel grid untuk melihat prakiraan satu jam ke depan.</p>
      </div>

      <div className="baris-kendali">
        <select value={dipilih} onChange={(e) => pilih(e.target.value)}>
          {tidakDikenal && (
            <option value={dipilih} disabled>
              Pilih lokasi…
            </option>
          )}
          {lokasi.map((l) => (
            <option key={l.kode_sel} value={l.kode_sel}>
              {admin ? `${l.kode_sel} — ${l.nama}` : l.nama}
            </option>
          ))}
        </select>
        <button
          disabled={tidakDikenal}
          onClick={() => navigasi(`/visualisasi/${dipilih}`)}
        >
          Lihat grafik riwayat
        </button>
      </div>

      {tidakDikenal && (
        <Galat
          pesan={`Lokasi dengan kode "${dipilih}" tidak ditemukan. Silakan pilih lokasi dari daftar di atas.`}
        />
      )}
      {!tidakDikenal && galat && (
        <Galat pesan="Prediksi belum dapat ditampilkan. Periksa koneksi Anda, lalu muat ulang halaman ini." />
      )}
      {!tidakDikenal && !data && !galat && <Memuat />}

      {!tidakDikenal && data && (
        <>
          <Kemutakhiran data={data.kemutakhiran} />

          {/* Pesan dari server dirender di sini. Sebelum 4 Oktober 2026 nilai
              ini dikirim API tetapi dibuang halaman, sehingga satu-satunya
              peringatan yang pernah terlihat adalah banner Kemutakhiran — dan
              banner itu menilai kesegaran PENGAMATAN, bukan kesegaran prediksi.
              Prediksi yang jam targetnya sudah lewat lolos tanpa tanda apa pun
              selama pengamatannya segar. */}
          {data.pesan && (
            <div className="catatan ingat" style={{ marginTop: ".6rem" }}>
              {data.pesan}
            </div>
          )}

          {!p && (
            <div className="catatan ingat" style={{ marginTop: "1rem" }}>
              Prediksi untuk lokasi ini belum tersedia.
            </div>
          )}

          {p && (
            <div className="kartu" style={{ marginTop: "1rem" }}>
              <div className="kecil">
                {admin ? `${p.kode_sel} · ${p.nama_lokasi}` : p.nama_lokasi}
              </div>
              <h3 style={{ marginTop: ".2rem" }}>
                Prakiraan untuk {tanggalPanjang(p.waktu_prediksi)} pukul{" "}
                {jam(p.waktu_prediksi, false)} WIB
              </h3>

              {/* Hubungan antara kedua jam disebut eksplisit. Judul di atas
                  adalah jam TARGET, sedangkan "Pengamatan terakhir" di tabel
                  bawah adalah jam DATA — selalu satu jam lebih awal. Tanpa
                  keterangan ini keduanya berdiri berdekatan tanpa penanda dan
                  mudah terbaca sebagai jam yang sama atau sebagai selisih yang
                  keliru. */}
              {p.waktu_dasar && (
                <div className="kecil">
                  Satu jam ke depan dari pengamatan pukul{" "}
                  {jam(p.waktu_dasar, false)} WIB.
                </div>
              )}

              <div className="sorot" style={{ margin: "1rem 0" }}>
                <span className="angka">{angka(p.nilai_so2, 1)}</span>
                <span className="satuan" style={{ fontSize: "1rem" }}>
                  µg/m³
                </span>
                <Lencana kategori={p.kategori} />
              </div>

              <div
                className={
                  p.melampaui_baku_mutu ? "catatan ingat" : "catatan info"
                }
              >
                {p.melampaui_baku_mutu ? (
                  <>
                    Melampaui baku mutu satu jam (150 µg/m³), yaitu{" "}
                    {angka(p.rasio_baku_mutu * 100, 0)}% dari baku mutu.
                  </>
                ) : (
                  <>
                    Memenuhi baku mutu satu jam (150 µg/m³), yaitu{" "}
                    {angka(p.rasio_baku_mutu * 100, 0)}% dari baku mutu.
                  </>
                )}
              </div>

              <h3 style={{ marginTop: "1.4rem" }}>Rincian</h3>
              <table>
                <tbody>
                  <tr>
                    <td>
                      Pengamatan terakhir (SO₂)
                      {data.kemutakhiran?.waktu_data_terakhir &&
                        ` · ${jam(data.kemutakhiran.waktu_data_terakhir)}`}
                    </td>
                    <td className="angka">
                      {angka(data.so2_terakhir, 1)} µg/m³
                    </td>
                  </tr>
                  <tr>
                    <td>Jam dasar prediksi</td>
                    <td className="angka">{jam(p.waktu_dasar)}</td>
                  </tr>
                  {admin && (
                    <>
                      <tr>
                        <td>Keluaran XGBoost</td>
                        <td className="angka">
                          {angka(p.nilai_xgboost)} µg/m³
                        </td>
                      </tr>
                      <tr>
                        <td>Keluaran Random Forest</td>
                        <td className="angka">
                          {angka(p.nilai_random_forest)} µg/m³
                        </td>
                      </tr>
                    </>
                  )}
                  <tr>
                    <td>
                      <b>Hasil Prediksi Stacking Ensemble</b>
                    </td>
                    <td className="angka">
                      <b>{angka(p.nilai_so2)} µg/m³</b>
                    </td>
                  </tr>
                  {p.nilai_aktual !== null && p.nilai_aktual !== undefined && (
                    <>
                      <tr>
                        <td>Nilai sebenarnya</td>
                        <td className="angka">{angka(p.nilai_aktual)} µg/m³</td>
                      </tr>
                      <tr>
                        <td>Selisih</td>
                        <td className="angka">{angka(p.selisih)} µg/m³</td>
                      </tr>
                    </>
                  )}
                  {admin && (
                    <tr>
                      <td>Dibentuk pada</td>
                      <td className="angka">{jam(p.dibuat_pada)}</td>
                    </tr>
                  )}
                </tbody>
              </table>

              {info && (
                <p className="kecil" style={{ marginTop: "1rem" }}>
                  {info.wilayah_administratif} · {info.karakteristik} · elevasi{" "}
                  {angka(info.elevasi, 0)} m
                </p>
              )}
            </div>
          )}
        </>
      )}
    </>
  );
}
