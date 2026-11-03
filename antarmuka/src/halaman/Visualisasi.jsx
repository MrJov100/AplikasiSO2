import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { panggil, angka, jam } from "../api.js";
import { Memuat, Galat } from "../komponen/Umum.jsx";

// Pilihan rentang waktu grafik, dalam jam.
const PILIHAN_JAM = [
  { nilai: 24, label: "24 jam" },
  { nilai: 72, label: "3 hari" },
  { nilai: 168, label: "7 hari" },
  { nilai: 720, label: "30 hari" },
];

// Halaman Visualisasi Riwayat: grafik SO₂ per jam satu sel terhadap garis baku mutu.
export default function Visualisasi({ admin }) {
  const { kodeSel } = useParams();
  const navigasi = useNavigate();
  const [lokasi, setLokasi] = useState([]);
  const [dipilih, setDipilih] = useState(kodeSel || "G04");
  const [rentang, setRentang] = useState(168);
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
    panggil(`/api/visualisasi/riwayat/${dipilih}?jam=${rentang}`)
      .then(setData)
      .catch((e) => setGalat(e.message));
  }, [dipilih, rentang]);

  // Mengganti sel yang dipilih dan menyelaraskan alamat halaman.
  function pilih(kode) {
    setDipilih(kode);
    navigasi(`/visualisasi/${kode}`, { replace: true });
  }

  const titik = (data?.titik || []).map((t) => ({
    waktu: t.waktu,
    label: jam(t.waktu),
    so2: Number(t.so2),
  }));
  const tertinggi = titik.length ? Math.max(...titik.map((t) => t.so2)) : 0;
  const info = lokasi.find((l) => l.kode_sel === dipilih);

  // Garis acuan baku mutu hanya ditampilkan bila mendekati rentang data, supaya
  // grafik tidak gepeng ketika konsentrasi jauh di bawah 150 µg/m³.
  const tampilkanBakuMutu = tertinggi > 90;

  return (
    <>
      <div className="kepala">
        <h1>Visualisasi Riwayat</h1>
        <p>Konsentrasi SO₂ per jam beserta garis acuan baku mutu.</p>
      </div>

      <div className="baris-kendali">
        <select value={dipilih} onChange={(e) => pilih(e.target.value)}>
          {lokasi.map((l) => (
            <option key={l.kode_sel} value={l.kode_sel}>
              {admin ? `${l.kode_sel} — ${l.nama}` : l.nama}
            </option>
          ))}
        </select>
        {PILIHAN_JAM.map((p) => (
          <button
            key={p.nilai}
            className={rentang === p.nilai ? "utama" : ""}
            onClick={() => setRentang(p.nilai)}
          >
            {p.label}
          </button>
        ))}
      </div>

      {galat && <Galat pesan={galat} />}
      {!data && !galat && <Memuat />}

      {data && (
        <div className="kartu">
          <h3>
            {admin ? `${dipilih} — ${info?.nama || ""}` : info?.nama || ""}
          </h3>
          <p className="kecil">
            {titik.length} jam terakhir · tertinggi {angka(tertinggi, 1)} µg/m³
            · baku mutu satu jam {angka(data.baku_mutu_satu_jam, 0)} µg/m³
          </p>

          <div style={{ width: "100%", height: 380, marginTop: ".75rem" }}>
            <ResponsiveContainer>
              <LineChart
                data={titik}
                margin={{ top: 8, right: 16, bottom: 4, left: 8 }}
              >
                <CartesianGrid stroke="#e7ecf1" vertical={false} />
                <XAxis
                  dataKey="label"
                  tick={{ fontSize: 11, fill: "#5b6b7a" }}
                  minTickGap={38}
                  tickLine={false}
                  axisLine={{ stroke: "#dde3e9" }}
                />
                <YAxis
                  tick={{ fontSize: 11, fill: "#5b6b7a" }}
                  tickLine={false}
                  axisLine={false}
                  width={56}
                  domain={[
                    0,
                    tampilkanBakuMutu ? "auto" : (d) => Math.ceil(d * 1.15),
                  ]}
                  label={{
                    value: "µg/m³",
                    angle: -90,
                    position: "insideLeft",
                    offset: 4,
                    dy: 20,
                    style: { fontSize: 11, fill: "#5b6b7a" },
                  }}
                />
                <Tooltip
                  formatter={(v) => [`${angka(v, 1)} µg/m³`, "SO₂"]}
                  labelFormatter={(l) => `Pukul ${l}`}
                />
                {tampilkanBakuMutu && (
                  <ReferenceLine
                    y={data.baku_mutu_satu_jam}
                    stroke="#b23a3a"
                    strokeDasharray="5 4"
                    label={{
                      value: "Baku mutu 150",
                      position: "insideTopRight",
                      fill: "#b23a3a",
                      fontSize: 11,
                    }}
                  />
                )}
                <Line
                  type="monotone"
                  dataKey="so2"
                  stroke="#16507a"
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 4 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </>
  );
}
