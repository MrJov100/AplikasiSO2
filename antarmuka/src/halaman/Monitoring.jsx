import { Fragment, useEffect, useState } from "react";
import { panggil, angka, jam } from "../api.js";
import { Memuat, Galat, Sorot, Halaman } from "../komponen/Umum.jsx";

// Jumlah baris riwayat sinkronisasi per halaman.
const PER_HALAMAN = 10;

// Kolom pengamatan yang boleh dikoreksi admin, beserta labelnya.
const KOLOM_BOLEH = [
  ["so2", "SO₂ (µg/m³)"],
  ["suhu", "Suhu (°C)"],
  ["kelembapan", "Kelembapan (%)"],
  ["titik_embun", "Titik embun (°C)"],
  ["curah_hujan", "Curah hujan (mm)"],
  ["tekanan_permukaan", "Tekanan (hPa)"],
  ["tutupan_awan", "Tutupan awan (%)"],
  ["kecepatan_angin", "Kecepatan angin (m/s)"],
  ["arah_angin", "Arah angin (°)"],
];

// Tab pada halaman Monitoring.
const TAB = [
  ["status", "Status per sel"],
  ["anomali", "Pengamatan ditandai"],
  ["koreksi", "Jejak koreksi"],
  ["siklus", "Riwayat sinkronisasi"],
];

/** Panel tindakan admin atas satu pengamatan.
 *
 * Tidak memakai window.confirm: dialog peramban memblokir seluruh halaman, dan
 * alasan koreksi memang harus ditulis, bukan sekadar diklik "ya".
 */
function PanelKoreksi({ baris, selesai, batal }) {
  const [tindakan, setTindakan] = useState(
    baris.status === "dikecualikan" ? "pulihkan" : "kecualikan",
  );
  const [alasan, setAlasan] = useState("");
  const [kolom, setKolom] = useState("so2");
  const [nilaiBaru, setNilaiBaru] = useState("");
  const [galat, setGalat] = useState(null);
  const [sedang, setSedang] = useState(false);

  // Mengirim tindakan koreksi ke server lalu memberi tahu induk bila berhasil.
  async function kirim() {
    setGalat(null);
    setSedang(true);
    try {
      const isi = { id_pengamatan: baris.id_pengamatan, tindakan, alasan };
      if (tindakan === "ubah_nilai") {
        isi.kolom_diubah = kolom;
        isi.nilai_baru = Number(nilaiBaru);
      }
      await panggil("/api/monitoring/koreksi", {
        method: "POST",
        body: JSON.stringify(isi),
      });
      selesai();
    } catch (e) {
      setGalat(e.message);
      setSedang(false);
    }
  }

  const siap =
    alasan.trim().length >= 5 &&
    (tindakan !== "ubah_nilai" || nilaiBaru !== "");

  // Tutup dengan Escape, seperti dialog Profil Admin.
  useEffect(() => {
    function padaTombol(e) {
      if (e.key === "Escape" && !sedang) batal();
    }
    window.addEventListener("keydown", padaTombol);
    return () => window.removeEventListener("keydown", padaTombol);
  }, [batal, sedang]);

  return (
    <div
      className="sorot-tirai"
      onClick={() => !sedang && batal()}
      role="dialog"
      aria-modal="true"
      aria-label="Koreksi pengamatan"
    >
      <div
        className="profil-kotak koreksi-kotak"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          className="profil-tutup"
          onClick={batal}
          disabled={sedang}
          aria-label="Tutup"
        >
          ×
        </button>
        <div>
          <h3>Koreksi pengamatan #{baris.id_pengamatan}</h3>
          <p className="kecil">
            {baris.kode_sel} · {jam(baris.waktu)} · SO₂ {angka(baris.so2)} µg/m³
            · status sekarang <b>{baris.status}</b>
          </p>

          <label className="medan">
            <span>Tindakan</span>
            <select
              value={tindakan}
              onChange={(e) => setTindakan(e.target.value)}
            >
              <option value="kecualikan">
                Kecualikan — tidak dipakai sebagai masukan model
              </option>
              <option value="pulihkan">
                Pulihkan — kembalikan ke status sah
              </option>
              <option value="ubah_nilai">
                Ubah nilai — perbaiki satu kolom
              </option>
              <option value="tandai_anomali">
                Tandai anomali — tandai untuk ditinjau
              </option>
            </select>
          </label>

          {tindakan === "ubah_nilai" && (
            <>
              <label className="medan">
                <span>Kolom</span>
                <select
                  value={kolom}
                  onChange={(e) => setKolom(e.target.value)}
                >
                  {KOLOM_BOLEH.map(([k, n]) => (
                    <option key={k} value={k}>
                      {n}
                    </option>
                  ))}
                </select>
              </label>
              <label className="medan">
                <span>Nilai baru (nilai sekarang {angka(baris[kolom])})</span>
                <input
                  type="number"
                  step="any"
                  value={nilaiBaru}
                  onChange={(e) => setNilaiBaru(e.target.value)}
                />
              </label>
            </>
          )}

          <label className="medan">
            <span>Alasan (wajib, tersimpan sebagai jejak audit)</span>
            <input
              value={alasan}
              onChange={(e) => setAlasan(e.target.value)}
              placeholder="misalnya: lonjakan sesaat, tidak sejalan jam sekitarnya"
            />
          </label>

          <div className="catatan info" style={{ marginBottom: ".75rem" }}>
            {tindakan === "kecualikan" &&
              "Barisnya tidak dihapus, hanya ditandai. Bila jam ini dibutuhkan sebagai lag t−1..t−3, prediksi jam tersebut akan ditolak dengan pesan jelas, bukan diam-diam memakai jam lain."}
            {tindakan === "ubah_nilai" &&
              "Baris yang pernah dikoreksi begini dilindungi: sinkronisasi berikutnya tidak akan menimpanya kembali dengan nilai dari sumber."}
            {tindakan === "pulihkan" &&
              "Status kembali menjadi sah dan barisnya kembali dipakai membentuk lag."}
            {tindakan === "tandai_anomali" &&
              "Status anomali berarti menunggu ditinjau. Baris anomali tetap dipakai membentuk lag — hanya keputusan manusia (kecualikan) yang memblokirnya."}
          </div>

          {galat && <Galat pesan={galat} />}

          <div className="baris-kendali">
            <button
              className="utama"
              disabled={!siap || sedang}
              onClick={kirim}
            >
              {sedang ? "Menyimpan…" : "Simpan koreksi"}
            </button>
            <button onClick={batal}>Batal</button>
          </div>
        </div>
      </div>
    </div>
  );
}

// Halaman Monitoring Data (admin): status per sel, pengamatan ditandai, jejak
// koreksi, riwayat sinkronisasi, serta pemicu sinkronisasi manual.
export default function Monitoring() {
  const [tab, setTab] = useState("status");
  const [data, setData] = useState(null);
  const [galat, setGalat] = useState(null);
  const [pilih, setPilih] = useState(null);
  const [sinkron, setSinkron] = useState(null);
  const [muatUlang, setMuatUlang] = useState(0);
  const [peringatan, setPeringatan] = useState(null);
  const [halaman, setHalaman] = useState(1);

  // Endpoint yang dimuat untuk tiap tab.
  const JALUR = {
    status: "/api/monitoring/status",
    anomali: "/api/monitoring/anomali?batas=300",
    koreksi: "/api/monitoring/koreksi?batas=200",
    siklus: "/api/monitoring/siklus?batas=50",
  };

  useEffect(() => {
    setData(null);
    setGalat(null);
    setPilih(null);
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
        <p>
          Kemutakhiran data tiap sel, pengamatan yang ditandai validator, dan
          jejak setiap koreksi admin.
        </p>
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
                <th className="angka">Pengamatan</th>
                <th className="angka">Ditandai</th>
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
                  <td className="angka">{b.jumlah_pengamatan}</td>
                  <td className="angka">{b.jumlah_anomali}</td>
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

      {data && tab === "anomali" && (
        <div className="kartu">
          <p className="kecil">
            {data.length} pengamatan berstatus bukan <i>sah</i>. Status{" "}
            <i>anomali</i> berarti menunggu ditinjau dan <b>tetap</b> dipakai
            membentuk lag; hanya <i>dikecualikan</i> yang memblokirnya.
          </p>
          <table>
            <thead>
              <tr>
                <th>Sel</th>
                <th>Waktu</th>
                <th className="angka">SO₂</th>
                <th>Status</th>
                <th>Alasan validator</th>
                <th className="angka">Angin</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {data.map((b) => (
                <Fragment key={b.id_pengamatan}>
                  <tr>
                    <td>{b.kode_sel}</td>
                    <td>{jam(b.waktu)}</td>
                    <td className="angka">{angka(b.so2)}</td>
                    <td>
                      <span
                        className={`lencana ${b.status === "dikecualikan" ? "abu" : "sedang"}`}
                      >
                        {b.status}
                      </span>
                    </td>
                    <td className="kecil">{b.alasan_anomali || "—"}</td>
                    <td className="angka">{angka(b.kecepatan_angin, 1)}</td>
                    <td>
                      <button
                        className="kecil"
                        onClick={() => setPilih(b.id_pengamatan)}
                      >
                        Tinjau
                      </button>
                    </td>
                  </tr>
                  {pilih === b.id_pengamatan && (
                    <PanelKoreksi
                      baris={b}
                      batal={() => setPilih(null)}
                      selesai={() => {
                        setPilih(null);
                        setMuatUlang((n) => n + 1);
                      }}
                    />
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
          {data.length === 0 && (
            <p className="kecil">Tidak ada pengamatan yang ditandai.</p>
          )}
        </div>
      )}

      {data && tab === "koreksi" && (
        <div className="kartu">
          <p className="kecil">
            {data.length} koreksi tercatat. Barisnya tidak pernah dihapus —
            inilah jejak audit tabel KOREKSI_PENGAMATAN.
          </p>
          <table>
            <thead>
              <tr>
                <th>Waktu koreksi</th>
                <th>Admin</th>
                <th>Sel</th>
                <th>Jam pengamatan</th>
                <th>Tindakan</th>
                <th>Kolom</th>
                <th className="angka">Lama</th>
                <th className="angka">Baru</th>
                <th>Alasan</th>
              </tr>
            </thead>
            <tbody>
              {data.map((k) => (
                <tr key={k.id_koreksi}>
                  <td>{jam(k.waktu_koreksi)}</td>
                  <td>{k.nama_lengkap}</td>
                  <td>{k.kode_sel}</td>
                  <td>{jam(k.waktu_pengamatan)}</td>
                  <td>{k.tindakan}</td>
                  <td className="kecil">{k.kolom_diubah || "—"}</td>
                  <td className="angka">{angka(k.nilai_lama)}</td>
                  <td className="angka">{angka(k.nilai_baru)}</td>
                  <td className="kecil">{k.alasan}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {data.length === 0 && <p className="kecil">Belum ada koreksi.</p>}
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
