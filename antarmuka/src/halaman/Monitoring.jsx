import { useEffect, useState } from "react";
import { panggil, jam } from "../api.js";
import { Memuat, Galat, Sorot, Halaman } from "../komponen/Umum.jsx";

// Jumlah baris riwayat sinkronisasi per halaman.
const PER_HALAMAN = 10;

// Tab pada halaman Monitoring.
const TAB = [
  ["status", "Status per sel"],
  ["siklus", "Riwayat sinkronisasi"],
];

// Halaman Monitoring Data (admin): status per sel, riwayat sinkronisasi, serta
// pemicu sinkronisasi manual.
export default function Monitoring() {
  const [tab, setTab] = useState("status");
  const [data, setData] = useState(null);
  const [galat, setGalat] = useState(null);
  const [sinkron, setSinkron] = useState(null);
  const [muatUlang, setMuatUlang] = useState(0);
  const [peringatan, setPeringatan] = useState(null);
  const [halaman, setHalaman] = useState(1);

  // Endpoint yang dimuat untuk tiap tab.
  const JALUR = {
    status: "/api/monitoring/status",
    siklus: "/api/monitoring/siklus?batas=50",
  };

  useEffect(() => {
    setData(null);
    setGalat(null);
    setHalaman(1);
    panggil(JALUR[tab])
      .then(setData)
      .catch((e) => setGalat(e.message));
  }, [tab, muatUlang]);

  // Peringatan ditarik terpisah dari tab yang sedang aktif.
  //
  // Sebelumnya kemutakhiran hanya terlihat sebagai lencana kecil di dalam tab
  // "Status per sel", dan kegagalan prediksi tidak terlihat sama sekali. Pada
  // 1 Oktober 2026 pukul 01.00-07.00 pengamatan tertinggal enam jam dan seluruh
  // prediksi tidak terbentuk, tetapi admin tidak mendapat tanda apa pun. Karena
  // itu kedua keadaan itu kini diangkat ke spanduk tingkat halaman, yang tampil
  // pada tab mana pun.
  useEffect(() => {
    Promise.all([
      panggil("/api/monitoring/status"),
      panggil("/api/monitoring/siklus?batas=1"),
    ])
      .then(([st, sk]) => setPeringatan({ sel: st, siklus: sk?.[0] ?? null }))
      .catch(() => setPeringatan(null));
  }, [muatUlang]);

  const selBasi = (peringatan?.sel ?? []).filter((b) => !b.mutakhir);
  const siklusTerakhir = peringatan?.siklus;
  const siklusBuruk =
    siklusTerakhir && ["gagal", "sebagian"].includes(siklusTerakhir.status);

  // Sinkronisasi manual memanggil Open-Meteo untuk setiap sel, jadi bisa
  // berjalan belasan detik. Keadaannya ditampilkan sebagai dialog mengambang
  // (Sorot), bukan spanduk di bawah baris tombol: admin yang sudah menggulir
  // tabel tidak melihat spanduk itu dan menyangka kliknya tidak berefek.
  async function sinkronisasiManual() {
    setSinkron({ sedang: true });
    try {
      const h = await panggil("/api/monitoring/sinkronisasi", {
        method: "POST",
      });
      setSinkron({ hasil: h });
      setMuatUlang((n) => n + 1);
    } catch (e) {
      setSinkron({ galat: e.message });
    }
  }

  // Siklus yang sebagian selnya gagal bukan keberhasilan penuh: ikonnya harus
  // merah agar admin menengok tab riwayat, bukan hijau yang menenangkan.
  //
  // Dasarnya STATUS gabungan ketiga langkah, bukan hanya hasil.gagal — jumlah
  // sel langkah PENARIKAN. Sampai 4 Oktober 2026 siklus dengan sepuluh sel
  // tertarik tetapi sepuluh prediksi gagal punya hasil.gagal 0, sehingga dialog
  // menyatakan "Sinkronisasi berhasil" dengan ikon hijau. Itu bentuk kegagalan
  // yang sama seperti 1 Oktober 2026, dan ia sudah diperbaiki pada lencana tabel
  // riwayat di bawah tetapi tertinggal di dialog ini.
  const h = sinkron?.hasil;
  const sinkronGagalSebagian = h
    ? h.status
      ? h.status !== "berhasil"
      : (h.gagal ?? 0) > 0 || (h.prediksi_gagal ?? 0) > 0
    : false;

  return (
    <>
      <div className="kepala">
        <h1>Monitoring Data</h1>
        <p>Kemutakhiran data dan hasil sinkronisasi tiap sel grid.</p>
      </div>

      <div className="baris-kendali baris-monitoring">
        <div className="tab-monitoring">
          {TAB.map(([k, n]) => (
            <button
              key={k}
              className={tab === k ? "utama" : ""}
              onClick={() => setTab(k)}
            >
              {n}
            </button>
          ))}
        </div>
        {/* Warna hijau tersendiri agar tidak tertukar dengan tombol tab. */}
        <button
          className="sinkron"
          onClick={sinkronisasiManual}
          disabled={sinkron?.sedang}
        >
          {sinkron?.sedang ? "Menyinkronkan…" : "⟳ Sinkronisasi sekarang"}
        </button>
      </div>

      {sinkron?.sedang && (
        <Sorot
          jenis="memuat"
          judul="Menyinkronkan data…"
          pesan="Menarik pengamatan terbaru untuk setiap sel, membentuk prediksi jam berikutnya, lalu mengisi nilai aktual. Mohon tunggu, jangan tutup halaman ini."
        />
      )}

      {sinkron?.hasil && (
        <Sorot
          jenis={sinkronGagalSebagian ? "galat" : "berhasil"}
          judul={
            h.status === "gagal"
              ? "Sinkronisasi gagal"
              : sinkronGagalSebagian
                ? "Sinkronisasi selesai sebagian"
                : "Sinkronisasi berhasil"
          }
          // Langkah prediksi ikut dilaporkan: tanpa itu admin tidak punya cara
          // membedakan siklus yang membentuk prediksi baru dari siklus yang
          // hanya menyegarkan pengamatan.
          pesan={
            `Pengamatan: ${h.berhasil ?? "?"} sel berhasil, ${h.gagal ?? "?"} gagal.` +
            (h.prediksi_berhasil != null
              ? ` Prediksi: ${h.prediksi_berhasil} berhasil, ${h.prediksi_gagal} gagal.`
              : "") +
            (h.aktual_terisi != null
              ? ` Nilai aktual terisi: ${h.aktual_terisi}.`
              : "") +
            (h.galat_penarikan?.length
              ? ` Penyebab penarikan gagal — ${h.galat_penarikan.join("; ")}`
              : "") +
            (h.galat_prediksi?.length
              ? ` Contoh galat — ${h.galat_prediksi.join("; ")}`
              : "")
          }
          tutup={() => setSinkron(null)}
        />
      )}

      {sinkron?.galat && (
        <Sorot
          jenis="galat"
          judul="Sinkronisasi gagal"
          pesan={sinkron.galat}
          tutup={() => setSinkron(null)}
        />
      )}

      {siklusBuruk && (
        <div className="catatan galat" style={{ marginBottom: "1rem" }}>
          <b>Siklus sinkronisasi terakhir {siklusTerakhir.status}.</b> Mulai{" "}
          {jam(siklusTerakhir.waktu_mulai)} — penarikan{" "}
          {siklusTerakhir.jumlah_berhasil} berhasil,{" "}
          {siklusTerakhir.jumlah_gagal} gagal
          {siklusTerakhir.prediksi_gagal != null && (
            <>
              ; prediksi {siklusTerakhir.prediksi_berhasil ?? 0} berhasil,{" "}
              {siklusTerakhir.prediksi_gagal} gagal
            </>
          )}
          .{" "}
          <button className="tautan" onClick={() => setTab("siklus")}>
            Lihat riwayat sinkronisasi
          </button>
        </div>
      )}

      {selBasi.length > 0 && (
        <div className="catatan galat" style={{ marginBottom: "1rem" }}>
          <b>
            {selBasi.length === (peringatan?.sel?.length ?? 0)
              ? "Seluruh sel"
              : `${selBasi.length} sel`}{" "}
            tidak mutakhir.
          </b>{" "}
          Paling tertinggal{" "}
          {Math.max(...selBasi.map((b) => b.tertinggal_jam ?? 0))} jam (
          {selBasi.map((b) => b.kode_sel).join(", ")}). Prediksi tidak dibentuk
          selama data belum mutakhir.{" "}
          <button className="tautan" onClick={() => setTab("status")}>
            Lihat status per sel
          </button>
        </div>
      )}

      {galat && <Galat pesan={galat} />}
      {!data && !galat && <Memuat />}

      {data && tab === "status" && (
        <div className="kartu">
          <table>
            <thead>
              <tr>
                <th>Sel</th>
                <th>Nama</th>
                <th>Data terakhir</th>
                <th className="angka">Tertinggal</th>
                <th>Mutakhir</th>
                <th>Sinkronisasi terakhir</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {data.map((b) => (
                <tr key={b.kode_sel}>
                  <td>
                    <b>{b.kode_sel}</b>
                  </td>
                  <td>{b.nama}</td>
                  <td>{jam(b.waktu_data_terakhir)}</td>
                  <td className="angka">
                    {b.tertinggal_jam === null
                      ? "—"
                      : `${b.tertinggal_jam} jam`}
                  </td>
                  <td>
                    <span
                      className={`lencana ${b.mutakhir ? "baik" : "sedang"}`}
                    >
                      {b.mutakhir ? "ya" : "tidak"}
                    </span>
                  </td>
                  <td>{jam(b.sinkronisasi_terakhir)}</td>
                  <td className="kecil">
                    {b.status_sinkronisasi || "—"}
                    {b.pesan_galat && (
                      <div style={{ color: "var(--sangat-buruk)" }}>
                        {b.pesan_galat}
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {data &&
        tab === "siklus" &&
        (() => {
          const totalHalaman = Math.max(
            1,
            Math.ceil(data.length / PER_HALAMAN),
          );
          const aktif = Math.min(halaman, totalHalaman);
          const mulai = (aktif - 1) * PER_HALAMAN;
          const tampil = data.slice(mulai, mulai + PER_HALAMAN);
          return (
            <div className="kartu">
              <p className="kecil">
                {data.length} siklus
                {data.length > 0 &&
                  ` · menampilkan ${mulai + 1}–${mulai + tampil.length}`}
              </p>
              <table>
                <thead>
                  <tr>
                    <th>Mulai</th>
                    <th>Selesai</th>
                    <th>Pemicu</th>
                    <th>Status</th>
                    <th className="angka">Tarik ok</th>
                    <th className="angka">Tarik gagal</th>
                    <th className="angka">Prediksi ok</th>
                    <th className="angka">Prediksi gagal</th>
                    <th className="angka">Aktual terisi</th>
                    <th>Keterangan</th>
                  </tr>
                </thead>
                <tbody>
                  {tampil.map((s) => (
                    <tr key={s.id_siklus}>
                      <td>{jam(s.waktu_mulai)}</td>
                      <td>{jam(s.waktu_selesai)}</td>
                      <td>{s.pemicu}</td>
                      <td>
                        {/* Lencana mengikuti STATUS, bukan jumlah_gagal: siklus
                        yang penarikannya lancar tetapi prediksinya habis gagal
                        punya jumlah_gagal 0 dan dulu tampil hijau.

                        'gagal' memakai kelasnya sendiri, bukan 'buruk' yang
                        oranye dan dipakai bersama skala kategori udara: siklus
                        yang gagal harus terbaca sebagai peringatan merah. */}
                        <span
                          className={`lencana ${
                            s.status === "berhasil"
                              ? "baik"
                              : s.status === "berjalan"
                                ? "abu"
                                : s.status === "sebagian"
                                  ? "sedang"
                                  : "gagal"
                          }`}
                        >
                          {s.status}
                        </span>
                      </td>
                      <td className="angka">{s.jumlah_berhasil}</td>
                      <td className="angka">{s.jumlah_gagal}</td>
                      <td className="angka">{s.prediksi_berhasil ?? "—"}</td>
                      <td className="angka">{s.prediksi_gagal ?? "—"}</td>
                      <td className="angka">{s.aktual_terisi ?? "—"}</td>
                      {/* Alasan kegagalan penarikan dalam bahasa admin, dan
                      kapan penarikan ulang otomatis berikutnya. */}
                      <td
                        className="kecil"
                        style={
                          s.keterangan
                            ? { color: "var(--sangat-buruk)", minWidth: "16rem" }
                            : undefined
                        }
                      >
                        {s.keterangan || "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {data.length === 0 && (
                <p className="kecil">Belum ada siklus tercatat.</p>
              )}
              <Halaman aktif={aktif} total={totalHalaman} onUbah={setHalaman} />
            </div>
          );
        })()}
    </>
  );
}
