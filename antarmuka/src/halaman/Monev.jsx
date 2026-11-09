import { useEffect, useState } from "react";
import { panggil, angka, jam, tanggalPanjang } from "../api.js";
import { Memuat, Galat, Halaman } from "../komponen/Umum.jsx";

// Jumlah baris Riwayat Peringatan per halaman.
const PER_HALAMAN = 10;

// Kelas lencana untuk tiap status perubahan. Peringatan memakai merah
// ('gagal') agar tidak tertukar dengan skala kategori kualitas udara.
const KELAS_STATUS = {
  Peringatan: "gagal",
  Naik: "sedang",
  Stabil: "abu",
  Turun: "baik",
};

// Memformat angka bertanda, mis. 8 → "+8.00", -1.5 → "-1.50".
function bertanda(n) {
  return `${n > 0 ? "+" : ""}${angka(n, 2)}`;
}

// Menampilkan besar perubahan dengan tanda dan panah arahnya, mis. "▲ +8.42".
// Dua desimal, sama dengan presisi penyimpanan, supaya angka yang tampil tidak
// pernah tampak melewati ambang padahal statusnya belum (mis. 7.96 → "8.0").
function Perubahan({ nilai, status }) {
  if (nilai === null || nilai === undefined) return "—";
  const panah = status === "Turun" ? "▼" : status === "Stabil" ? "▶" : "▲";
  const kelas = `arah-${(status || "stabil").toLowerCase()}`;
  return (
    <span className={kelas}>
      {panah} {bertanda(nilai)}
    </span>
  );
}

// Lencana berwarna untuk status perubahan satu sel.
function LencanaStatus({ status }) {
  if (!status) return <span className="lencana abu">Tanpa pembanding</span>;
  return (
    <span className={`lencana ${KELAS_STATUS[status] || "abu"}`}>{status}</span>
  );
}

// Keterangan rentang perubahan untuk setiap status. Perubahan disimpan dan
// ditampilkan dengan dua desimal, sehingga batas atas tiap rentang adalah
// batas bawah status berikutnya dikurangi 0.01.
function LegendaStatus({ ambang, pita }) {
  const rentang = [
    ["Peringatan", `${bertanda(ambang)} µg/m³ atau lebih`],
    ["Naik", `${bertanda(pita)} sampai ${bertanda(ambang - 0.01)} µg/m³`],
    ["Stabil", `${bertanda(-(pita - 0.01))} sampai ${bertanda(pita - 0.01)} µg/m³`],
    ["Turun", `${bertanda(-pita)} µg/m³ atau kurang`],
  ];
  return (
    <div className="legenda-monev">
      {rentang.map(([status, teks]) => (
        <div key={status}>
          <LencanaStatus status={status} />
          <span>{teks}</span>
        </div>
      ))}
    </div>
  );
}

// Penanda waktu Kondisi Terkini yang mudah dibaca: jam data yang menjadi dasar
// perbandingan dan jam yang diprediksi, masing-masing beserta tanggalnya.
function WaktuKondisi({ dasar, target }) {
  return (
    <div className="waktu-monev">
      <div>
        <span className="label">Data pukul</span>
        <span className="nilai">{jam(dasar, false)} WIB</span>
        <span className="tanggal">{tanggalPanjang(dasar)}</span>
      </div>
      <div className="panah" aria-hidden="true">
        →
      </div>
      <div>
        <span className="label">Prediksi untuk pukul</span>
        <span className="nilai">{jam(target, false)} WIB</span>
        <span className="tanggal">{tanggalPanjang(target)}</span>
      </div>
    </div>
  );
}

// Menampilkan persentase dengan satu desimal; "—" bila belum dapat dihitung.
function persen(n) {
  return n === null || n === undefined ? "—" : `${angka(n, 1)}%`;
}

// Halaman MonEv SO₂ — Monitoring dan Evaluasi SO₂ (admin): memantau perubahan
// konsentrasi SO₂ satu jam ke depan tiap sel grid dan mengevaluasi ketepatan
// peringatannya. Halaman ini hanya menampilkan data; tidak ada perubahan data.
export default function Monev() {
  const [data, setData] = useState(null);
  const [galat, setGalat] = useState(null);
  const [halaman, setHalaman] = useState(1);

  // Memuat seluruh isi halaman sekali saat halaman dibuka.
  useEffect(() => {
    panggil("/api/monev/ringkasan")
      .then(setData)
      .catch((e) => setGalat(e.message));
  }, []);

  if (galat) return <Galat pesan={galat} />;
  if (!data) return <Memuat />;

  const ambang = data.ambang_peringatan;
  const pita = data.pita_stabil;
  const kondisi = data.kondisi;
  const diperingatkan = kondisi.filter((k) => k.status === "Peringatan");
  // Jam dasar dan jam target terbaru di antara seluruh sel, untuk keterangan.
  const terbaru = kondisi.reduce(
    (a, k) => (!a || k.waktu_prediksi > a.waktu_prediksi ? k : a),
    null,
  );
  const adaBasi = kondisi.some((k) => k.prediksi_basi);

  // Potongan Riwayat Peringatan untuk halaman yang sedang dibuka.
  const totalHalaman = Math.max(1, Math.ceil(data.riwayat.length / PER_HALAMAN));
  const aktif = Math.min(halaman, totalHalaman);
  const mulai = (aktif - 1) * PER_HALAMAN;
  const tampil = data.riwayat.slice(mulai, mulai + PER_HALAMAN);

  return (
    <>
      <div className="kepala">
        <h1>Monitoring dan Evaluasi SO₂</h1>
        <p>
          Pemantauan perubahan konsentrasi SO₂ satu jam ke depan pada sepuluh
          sel grid, beserta evaluasi ketepatan peringatannya.
        </p>
      </div>

      {kondisi.length === 0 && (
        <div className="catatan ingat" style={{ marginBottom: "1rem" }}>
          Belum ada prediksi tersimpan.
        </div>
      )}

      {kondisi.length > 0 &&
        (diperingatkan.length > 0 ? (
          <div className="catatan galat" style={{ marginBottom: "1rem" }}>
            <b>
              ⚠ {diperingatkan.length} wilayah diprediksi naik signifikan (
              {bertanda(ambang)} µg/m³ atau lebih) untuk pukul{" "}
              {jam(diperingatkan[0].waktu_prediksi, false)}:
            </b>{" "}
            {diperingatkan
              .map((k) => `${k.nama} (${bertanda(k.perubahan)} µg/m³)`)
              .join(" · ")}
          </div>
        ) : (
          <div className="catatan info" style={{ marginBottom: "1rem" }}>
            Tidak ada kenaikan signifikan yang diprediksi untuk pukul{" "}
            {jam(terbaru?.waktu_prediksi, false)}.
          </div>
        ))}

      {adaBasi && (
        <div className="catatan ingat" style={{ marginBottom: "1rem" }}>
          Sebagian prediksi sudah lewat waktunya dan belum diganti yang baru,
          sehingga status di bawah berasal dari pembaruan sebelumnya.
        </div>
      )}

      {kondisi.length > 0 && (
        <div className="kartu">
          <h3>Kondisi Terkini</h3>
          <WaktuKondisi
            dasar={terbaru?.waktu_dasar}
            target={terbaru?.waktu_prediksi}
          />
          <LegendaStatus ambang={ambang} pita={pita} />
          <table className="tabel-monev">
            <thead>
              <tr>
                <th>Sel</th>
                <th>Nama</th>
                <th className="angka">Teramati</th>
                <th className="angka">Prediksi</th>
                <th className="angka">Perubahan</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {kondisi.map((k) => (
                <tr key={k.kode_sel}>
                  <td>
                    <b>{k.kode_sel}</b>
                  </td>
                  <td>{k.nama}</td>
                  <td className="angka">{angka(k.so2_dasar, 1)}</td>
                  <td className="angka">{angka(k.nilai_so2, 2)}</td>
                  <td className="angka">
                    <Perubahan nilai={k.perubahan} status={k.status} />
                  </td>
                  <td>
                    <LencanaStatus status={k.status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="kecil" style={{ marginTop: ".6rem" }}>
            Satuan µg/m³. Perubahan = prediksi satu jam ke depan − konsentrasi
            teramati pada jam data.
          </p>
        </div>
      )}

      <div className="kartu">
        <h3>Evaluasi Peringatan</h3>
        <p className="kecil">
          Peringatan dinyatakan terbukti bila kenaikan aktualnya juga{" "}
          {bertanda(ambang)} µg/m³ atau lebih. Setiap jendela dihitung mundur
          dari prediksi terbaru yang tersimpan
          {data.acuan && <> (untuk pukul {jam(data.acuan)})</>}, bukan dari jam
          saat ini.
        </p>
        {data.evaluasi.length === 0 ? (
          <p className="kecil">Belum ada prediksi yang dapat dievaluasi.</p>
        ) : (
          <table className="tabel-monev">
            <thead>
              <tr>
                <th>Ukuran</th>
                {data.evaluasi.map((e) => (
                  <th key={e.hari} className="angka">
                    {e.hari} hari terakhir
                    <div className="rentang-jendela">
                      {jam(e.mulai)} – {jam(e.akhir)}
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {[
                ["Prediksi dievaluasi", (e) => e.dievaluasi],
                ["Peringatan", (e) => e.peringatan],
                ["Terbukti", (e) => e.terbukti],
                ["Presisi", (e) => persen(e.presisi)],
                [
                  `Kenaikan aktual ${bertanda(ambang)} atau lebih`,
                  (e) => e.kenaikan_aktual,
                ],
                ["Tertangkap", (e) => persen(e.tertangkap)],
                ["Kenaikan terlewat", (e) => e.terlewat],
              ].map(([label, isi]) => (
                <tr key={label}>
                  <td>{label}</td>
                  {data.evaluasi.map((e) => (
                    <td key={e.hari} className="angka">
                      {isi(e)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <p className="kecil" style={{ marginTop: ".6rem" }}>
          Presisi = peringatan yang terbukti ÷ seluruh peringatan. Tertangkap =
          kenaikan aktual yang didahului peringatan ÷ seluruh kenaikan aktual.
          Kenaikan terlewat = kenaikan aktual yang tidak didahului peringatan.
        </p>
      </div>

      <div className="kartu">
        <h3>Riwayat Peringatan</h3>
        <p className="kecil">
          {data.riwayat.length} peringatan dalam {data.hari_riwayat} hari
          terakhir
          {data.riwayat_mulai && (
            <>
              {" "}
              ({jam(data.riwayat_mulai)} – {jam(data.acuan)})
            </>
          )}
          {data.riwayat.length > 0 &&
            ` · menampilkan ${mulai + 1}–${mulai + tampil.length}`}
        </p>
        {data.riwayat.length === 0 ? (
          <p className="kecil">
            Tidak ada peringatan dalam {data.hari_riwayat} hari terakhir.
          </p>
        ) : (
          <>
            <table className="tabel-monev">
              <thead>
                <tr>
                  <th>Untuk jam</th>
                  <th>Sel</th>
                  <th>Nama</th>
                  <th className="angka">Teramati</th>
                  <th className="angka">Prediksi</th>
                  <th className="angka">Aktual</th>
                  <th className="angka">Δ Prediksi</th>
                  <th className="angka">Δ Aktual</th>
                  <th>Terbukti</th>
                </tr>
              </thead>
              <tbody>
                {tampil.map((r) => (
                  <tr key={`${r.kode_sel}-${r.waktu_prediksi}`}>
                    <td>{jam(r.waktu_prediksi)}</td>
                    <td>
                      <b>{r.kode_sel}</b>
                    </td>
                    <td>{r.nama}</td>
                    <td className="angka">{angka(r.so2_dasar, 1)}</td>
                    <td className="angka">{angka(r.nilai_so2, 2)}</td>
                    <td className="angka">{angka(r.nilai_aktual, 1)}</td>
                    <td className="angka">{bertanda(r.perubahan_prediksi)}</td>
                    <td className="angka">
                      {r.perubahan_aktual === null
                        ? "—"
                        : bertanda(r.perubahan_aktual)}
                    </td>
                    <td>
                      {r.terbukti === null ? (
                        <span className="lencana abu">Menunggu</span>
                      ) : r.terbukti ? (
                        <span className="lencana baik">Ya</span>
                      ) : (
                        <span className="lencana sedang">Tidak</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <Halaman aktif={aktif} total={totalHalaman} onUbah={setHalaman} />
          </>
        )}
      </div>
    </>
  );
}
