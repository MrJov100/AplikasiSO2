import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { panggil, angka, jam } from "../api.js";
import { Lencana, Memuat, Galat } from "../komponen/Umum.jsx";

// Halaman Beranda: prediksi terbaru kesepuluh sel grid sekaligus.
// `admin`: kode sel (G01–G10) hanya ditampilkan bagi admin.
export default function Beranda({ admin }) {
  const [data, setData] = useState(null);
  const [galat, setGalat] = useState(null);
  const navigasi = useNavigate();

  useEffect(() => {
    panggil("/api/prediksi/terkini")
      .then(setData)
      .catch((e) => setGalat(e.message));
  }, []);

  if (galat) return <Galat pesan={galat} />;
  if (!data) return <Memuat />;

  const adaPrediksi = data.length > 0;

  return (
    <>
      <div className="kepala">
        <h1>Prediksi Konsentrasi SO₂ Jabodetabek</h1>
        <p>
          Prakiraan konsentrasi sulfur dioksida satu jam ke depan pada sepuluh
          sel grid Jabodetabek.
        </p>
      </div>

      {!adaPrediksi && (
        <div className="catatan ingat">
          Belum ada prediksi tersimpan. Jalankan penjadwal, atau bentuk prediksi
          secara manual, lalu muat ulang halaman ini.
        </div>
      )}

      {adaPrediksi && (
        <>
          <div className="petak">
            {data.map((p) => (
              <div
                key={p.kode_sel}
                className="kartu sel-kartu"
                onClick={() => navigasi(`/prediksi/${p.kode_sel}`)}
              >
                {admin && <div className="kode">{p.kode_sel}</div>}
                <div className="nama">{p.nama_lokasi}</div>
                <div>
                  <span className="nilai">{angka(p.nilai_so2, 1)}</span>
                  <span className="satuan">µg/m³</span>
                </div>
                <div style={{ marginTop: ".55rem" }}>
                  <Lencana kategori={p.kategori} />
                </div>
                <div className="jam">
                  untuk pukul {jam(p.waktu_prediksi)}
                  {p.kemutakhiran && !p.kemutakhiran.mutakhir && (
                    <> · data tertinggal {p.kemutakhiran.tertinggal_jam} jam</>
                  )}
                </div>
              </div>
            ))}
          </div>

          <div className="catatan info" style={{ marginTop: "1.25rem" }}>
            Nilai yang ditampilkan adalah <b>prakiraan</b>, bukan hasil
            pengukuran alat di lapangan. Baku mutu satu jam menurut PP 22/2021
            adalah 150 µg/m³. Klik salah satu sel untuk melihat rinciannya.
          </div>
        </>
      )}
    </>
  );
}
