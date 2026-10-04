import { useEffect, useState } from "react";
import { panggil, angka } from "../api.js";
import { Memuat, Galat } from "../komponen/Umum.jsx";

// Halaman Tentang: menerangkan asal data, cakupan, dan batas pemakaian.
// Isinya ditarik dari /api/informasi/tentang supaya angka ambang dan versi
// model tidak ditulis dua kali di berkas yang berbeda.
export default function Tentang() {
  const [data, setData] = useState(null);
  const [galat, setGalat] = useState(null);

  const [lokasi, setLokasi] = useState([]);

  useEffect(() => {
    panggil("/api/informasi/tentang")
      .then(setData)
      .catch((e) => setGalat(e.message));
    panggil("/api/informasi/lokasi")
      .then(setLokasi)
      .catch(() => {});
  }, []);

  const namaSel = (kode) =>
    lokasi.find((l) => l.kode_sel === kode)?.nama ?? kode;

  if (galat) return <Galat pesan={galat} />;
  if (!data) return <Memuat />;

  return (
    <>
      <div className="kepala">
        <h1>Tentang Aplikasi</h1>
        <p>Sumber data, ambang kategori, dan variabel masukan model prediksi SO₂</p>
      </div>

      <div className="kartu">
        <h3>Apa yang dikerjakan aplikasi ini</h3>
        <p>{data.keterangan}</p>
      </div>

      <div className="kartu">
        <h3>Sumber data</h3>
        <p>{data.sumber_data}</p>
        <div className="catatan ingat">
          Karena sumbernya keluaran model numerik, angka pada aplikasi ini tidak
          dapat disamakan dengan hasil pengukuran stasiun pemantauan, dan tidak
          ditujukan untuk keperluan resmi.
        </div>
      </div>

      <div className="kartu">
        <h3>Ambang kategori</h3>
        <p className="kecil">
          Baku mutu satu jam menurut PP 22/2021 adalah{" "}
          {angka(data.baku_mutu_satu_jam, 0)} {data.satuan}. Kategori di bawah
          ini bukan ISPU dan bukan European AQI.
        </p>
        <table>
          <thead>
            <tr>
              <th>Kategori</th>
              <th className="angka">Batas atas ({data.satuan})</th>
            </tr>
          </thead>
          <tbody>
            {data.ambang_kategori.map((a) => (
              <tr key={a.nama}>
                <td>{a.nama}</td>
                <td className="angka">
                  {a.batas_atas === null
                    ? "di atas ambang terakhir"
                    : angka(a.batas_atas, 0)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="kartu">
        <h3>Variabel masukan model</h3>
        <table>
          <thead>
            <tr>
              <th>Variabel</th>
              <th>Satuan</th>
              <th>Dipakai pada sel</th>
            </tr>
          </thead>
          <tbody>
            {data.variabel.map((v) => (
              <tr key={v.nama}>
                <td>{v.nama}</td>
                <td>{v.satuan}</td>
                <td>
                  {v.sel.length === 10
                    ? "Semua sel"
                    : v.sel.map(namaSel).join(", ")}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="kecil" style={{ marginTop: ".75rem" }}>
          Variabel meteorologi dipilih per sel dengan mutual information; hanya
          yang lolos seleksi yang ditampilkan. Setiap variabel dipakai pada tiga
          jam terakhir (t−1, t−2, t−3). Bila ketertinggalan data melebihi{" "}
          {data.batas_kemutakhiran_jam} jam, sistem menahan diri daripada
          menampilkan prediksi untuk jam yang sudah lewat.
        </p>
      </div>

      <div className="kartu">
        <h3>Penelitian</h3>
        <p>
          Aplikasi ini adalah luaran skripsi Program Studi Teknik Informatika,
          Fakultas Teknologi Informasi, Universitas Tarumanagara.
        </p>
        <table>
          <tbody>
            <tr>
              <td>Penyusun</td>
              <td>{data.peneliti.nama}</td>
            </tr>
            <tr>
              <td>NIM</td>
              <td>{data.peneliti.nim}</td>
            </tr>
            <tr>
              <td>Program studi</td>
              <td>{data.peneliti.program_studi}</td>
            </tr>
            {data.pembimbing.map((p) => (
              <tr key={p.peran}>
                <td>{p.peran}</td>
                <td>{p.nama}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
